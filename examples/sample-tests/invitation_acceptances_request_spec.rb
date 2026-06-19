# frozen_string_literal: true

require "rails_helper"

# Request spec for the public invitation_acceptances endpoints (EX-218).
#
# This is the feature's ONLY unauthenticated surface, so it gets the heaviest
# negative-path budget: a bad token must 404 with no shape leak, an expired token
# must mint no member, and a re-click on an accepted link must not double-create.
# Negative cases lead; the valid-accept happy path is asserted last. The org is
# derived FROM the invitation — never from a request param — so the final example
# pins that an attacker-supplied org param is ignored.
RSpec.describe "InvitationAcceptances", type: :request do
  let(:organization) { create(:organization) }
  let(:owner)        { create(:member, :owner, organization: organization) }

  let(:invitation) do
    create(:invitation, organization: organization, invited_by: owner,
                        email: "sam@acme.com", role: "agent", status: "pending",
                        expires_at: 7.days.from_now)
  end

  def setup_params
    { member: { name: "Sam Newbie", password: "correct horse battery staple" } }
  end

  # ---------------------------------------------------------------------------
  # Unknown token — 404, not 401, with no hint a token "almost" matched.
  # ---------------------------------------------------------------------------
  describe "unknown token" do
    it "returns 404 (not 401) and creates no member" do
      expect {
        get invitation_acceptance_path(token: "totally-bogus-token")
      }.not_to change(Member, :count)

      expect(response).to have_http_status(:not_found)
      expect(response).not_to have_http_status(:unauthorized)
    end

    it "does not leak token shape — a well-formed-looking miss still 404s" do
      lookalike = SecureRandom.urlsafe_base64(32) # right shape, wrong value
      get invitation_acceptance_path(token: lookalike)

      expect(response).to have_http_status(:not_found)
      expect(response.body).not_to include("digest")
    end
  end

  # ---------------------------------------------------------------------------
  # Expired token — shows the expired screen, mints no member.
  # ---------------------------------------------------------------------------
  describe "expired token" do
    let(:expired) do
      create(:invitation, organization: organization, invited_by: owner,
                          email: "old@acme.com", status: "pending", expires_at: 1.day.ago)
    end

    it "shows the expired screen and creates no member on show" do
      raw = expired.raw_token

      expect {
        get invitation_acceptance_path(token: raw)
      }.not_to change(Member, :count)

      expect(response.body).to include("no longer valid").or include("expired")
    end

    it "refuses to finalize an expired invite and creates no member on update" do
      raw = expired.raw_token

      expect {
        patch invitation_acceptance_path(token: raw), params: setup_params
      }.not_to change(Member, :count)

      expect(expired.reload.status).not_to eq("accepted")
    end
  end

  # ---------------------------------------------------------------------------
  # Idempotency — a second accept on an already-accepted link (now signed in)
  # redirects without creating a duplicate member.
  # ---------------------------------------------------------------------------
  describe "second accept on an already-accepted link" do
    it "redirects to the dashboard and does not create a duplicate member" do
      raw = invitation.raw_token

      # First acceptance mints the member and signs the invitee in.
      patch invitation_acceptance_path(token: raw), params: setup_params
      expect(invitation.reload.status).to eq("accepted")
      member_count = Member.count

      # Second click on the same link, now authenticated.
      expect {
        get invitation_acceptance_path(token: raw)
      }.not_to change(Member, :count)

      expect(response).to have_http_status(:found).or have_http_status(:see_other)
      expect(Member.count).to eq(member_count)
    end
  end

  # ---------------------------------------------------------------------------
  # Tenant binding — acceptance ignores any org param and binds to the
  # invitation's org. A crafted organization_id can never redirect the membership.
  # ---------------------------------------------------------------------------
  describe "org binding" do
    it "ignores an injected organization_id and binds the member to the invite's org" do
      attacker_org = create(:organization)
      raw = invitation.raw_token

      patch invitation_acceptance_path(token: raw),
            params: setup_params.merge(organization_id: attacker_org.id)

      member = Member.order(:created_at).last
      expect(member.organization).to eq(organization)   # the inviting org
      expect(member.organization).not_to eq(attacker_org)
    end
  end

  # ---------------------------------------------------------------------------
  # Happy path — valid token + setup creates the member in the inviting org at
  # the invited role and marks the invite accepted. Asserted last.
  # ---------------------------------------------------------------------------
  describe "valid acceptance" do
    it "creates a Member in the inviting org with the invited role and marks accepted" do
      raw = invitation.raw_token

      expect {
        patch invitation_acceptance_path(token: raw), params: setup_params
      }.to change(Member, :count).by(1)

      member = Member.order(:created_at).last
      expect(member.organization).to eq(organization)
      expect(member.role).to eq("agent")           # the role on the invitation
      expect(member.email).to eq("sam@acme.com")   # bound to the invited email

      expect(invitation.reload.status).to eq("accepted")
      expect(invitation.accepted_at).to be_present
    end
  end
end
