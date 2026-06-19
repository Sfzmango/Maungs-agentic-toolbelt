# frozen_string_literal: true

require "rails_helper"

# Request spec for the owner-only settings/invitations endpoints (EX-218).
#
# Negative-path-first: authorization denial and the mandatory cross-tenant 404
# come before the happy-path 201. Every action runs through
# current_organization.invitations — never Invitation.find — so an owner of one
# org can never name another org's invite. The accept route is covered separately
# in invitation_acceptances_request_spec.rb (it's the only unauthenticated surface).
RSpec.describe "Settings::Invitations", type: :request do
  let(:organization) { create(:organization) }
  let(:owner)        { create(:member, :owner,  organization: organization) }
  let(:agent)        { create(:member, :agent,  organization: organization) }
  let(:viewer)       { create(:member, :viewer, organization: organization) }

  def valid_params(email: "sam@acme.com", role: "viewer")
    { invitation: { email: email, role: role } }
  end

  # ---------------------------------------------------------------------------
  # Authorization — invite/list/revoke/resend is owner-only via MemberPolicy.
  # ---------------------------------------------------------------------------
  describe "authorization denial" do
    it "forbids an agent from creating an invitation (403, no row)" do
      sign_in agent

      expect {
        post settings_invitations_path, params: valid_params
      }.not_to change(Invitation, :count)

      expect(response).to have_http_status(:forbidden)
    end

    it "forbids a viewer from creating an invitation (403, no row)" do
      sign_in viewer

      expect {
        post settings_invitations_path, params: valid_params
      }.not_to change(Invitation, :count)

      expect(response).to have_http_status(:forbidden)
    end

    it "forbids a non-owner from revoking an invitation" do
      invitation = create(:invitation, organization: organization, invited_by: owner)
      sign_in agent

      delete settings_invitation_path(invitation)

      expect(response).to have_http_status(:forbidden)
      expect(invitation.reload.status).to eq("pending") # untouched
    end
  end

  # ---------------------------------------------------------------------------
  # Cross-tenant — the load-bearing isolation rule. Acting on another org's
  # invite resolves to 404 (NOT 403): a 403 would leak that the invite exists.
  # ---------------------------------------------------------------------------
  describe "cross-tenant isolation" do
    let(:org_b)       { create(:organization) }
    let(:org_b_owner) { create(:member, :owner, organization: org_b) }
    let!(:org_b_invite) do
      create(:invitation, organization: org_b, invited_by: org_b_owner, email: "lee@beta.com")
    end

    before { sign_in owner } # owner of Org A

    it "returns 404 (not 403) when revoking Org B's invitation" do
      delete settings_invitation_path(org_b_invite)

      expect(response).to have_http_status(:not_found)
      expect(org_b_invite.reload.status).to eq("pending") # not revoked
    end

    it "returns 404 when resending Org B's invitation" do
      post resend_settings_invitation_path(org_b_invite)

      expect(response).to have_http_status(:not_found)
    end
  end

  # ---------------------------------------------------------------------------
  # Validation — inviting someone already on the team is a 422 inline error,
  # and no invitation row is written.
  # ---------------------------------------------------------------------------
  describe "validation failure" do
    it "returns 422 with an inline error and creates no row for an existing member" do
      existing = create(:member, :agent, organization: organization, email: "ana@acme.com")
      sign_in owner

      expect {
        post settings_invitations_path, params: valid_params(email: existing.email)
      }.not_to change(Invitation, :count)

      expect(response).to have_http_status(:unprocessable_entity)
      expect(response.body).to include("already on your team")
    end

    it "returns 422 for a malformed email and creates no row" do
      sign_in owner

      expect {
        post settings_invitations_path, params: valid_params(email: "not-an-email")
      }.not_to change(Invitation, :count)

      expect(response).to have_http_status(:unprocessable_entity)
    end
  end

  # ---------------------------------------------------------------------------
  # Idempotency — re-inviting an email that already has an open pending invite
  # reuses the SAME row and resends, rather than creating a duplicate (which the
  # partial-unique index would reject anyway).
  # ---------------------------------------------------------------------------
  describe "re-inviting an open pending email" do
    it "reuses the existing row and resends — no duplicate created" do
      existing = create(:invitation, organization: organization, invited_by: owner,
                                    email: "sam@acme.com", status: "pending")
      sign_in owner

      expect {
        post settings_invitations_path, params: valid_params(email: "sam@acme.com")
      }.not_to change(Invitation, :count)

      expect(response).to have_http_status(:created)
      expect(existing.reload.status).to eq("pending")
      expect(enqueued_jobs.map { |j| j["job_class"] }).to include("InvitationMailerJob")
    end
  end

  # ---------------------------------------------------------------------------
  # Revoke — flips status to revoked, and the link stops working afterward.
  # ---------------------------------------------------------------------------
  describe "revoke" do
    it "flips the status to revoked" do
      invitation = create(:invitation, organization: organization, invited_by: owner)
      sign_in owner

      delete settings_invitation_path(invitation)

      expect(response).to have_http_status(:see_other).or have_http_status(:ok)
      expect(invitation.reload.status).to eq("revoked")
    end

    it "stops the acceptance link from working once revoked" do
      invitation = create(:invitation, organization: organization, invited_by: owner)
      raw = invitation.raw_token
      sign_in owner
      delete settings_invitation_path(invitation)

      # The public accept surface now treats the revoked invite as no-longer-valid,
      # and no member is minted.
      expect {
        get invitation_acceptance_path(token: raw)
      }.not_to change(Member, :count)

      expect(response).not_to have_http_status(:ok).and have_http_status(:created)
    end
  end

  # ---------------------------------------------------------------------------
  # Happy path — table stakes, asserted last.
  # ---------------------------------------------------------------------------
  describe "owner creates an invitation" do
    it "returns 201, writes the row in the owner's org, and enqueues the mailer" do
      sign_in owner

      expect {
        post settings_invitations_path, params: valid_params(email: "newbie@acme.com", role: "agent")
      }.to change(Invitation, :count).by(1)

      expect(response).to have_http_status(:created)

      invitation = Invitation.order(:created_at).last
      expect(invitation.organization).to eq(organization)
      expect(invitation.email).to eq("newbie@acme.com")
      expect(invitation.role).to eq("agent")
      expect(invitation.status).to eq("pending")
      expect(enqueued_jobs.map { |j| j["job_class"] }).to include("InvitationMailerJob")
    end
  end
end
