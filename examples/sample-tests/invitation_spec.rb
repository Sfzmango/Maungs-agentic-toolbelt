# frozen_string_literal: true

require "rails_helper"

# Model spec for the EX-218 Invitation model.
#
# Negative-path-first, per the @test-author catalog: we lead with the secret-handling
# guarantee (the raw token must never hit the database) and the data-integrity guards
# (the partial-unique index, the lifecycle scope), then confirm the one happy-path
# fact at the end. Every example below names the behavior it pins.
RSpec.describe Invitation, type: :model do
  let(:organization) { create(:organization) }
  let(:owner)        { create(:member, :owner, organization: organization) }

  # ---------------------------------------------------------------------------
  # Secret handling — the load-bearing security invariant: email the raw token,
  # persist only its SHA-256 digest. A DB leak must never yield a usable link.
  # ---------------------------------------------------------------------------
  describe "token handling" do
    it "persists only the digest and never the raw token" do
      invitation = build(:invitation, organization: organization, invited_by: owner)
      raw = invitation.generate_token! # returns the raw token, sets token_digest

      invitation.save!

      # The raw token is emailed, not stored; nothing in the row equals it.
      stored = invitation.attributes.values.map(&:to_s)
      expect(stored).not_to include(raw)

      # What IS stored is the SHA-256 digest of the raw token.
      expect(invitation.token_digest).to eq(Digest::SHA256.hexdigest(raw))
      expect(invitation.token_digest).not_to eq(raw)
    end

    it "reloads from the DB without ever exposing the raw token" do
      invitation = create(:invitation, organization: organization, invited_by: owner)
      reloaded = described_class.find(invitation.id)

      expect(reloaded).not_to respond_to(:token) # no plaintext accessor at rest
      expect(reloaded.token_digest).to be_present
    end

    it "looks up by hashing the incoming raw token, not by storing it" do
      invitation = create(:invitation, organization: organization, invited_by: owner)
      raw = invitation.raw_token # captured at creation, only in memory

      found = described_class.find_by(token_digest: Digest::SHA256.hexdigest(raw))
      expect(found).to eq(invitation)

      # A garbage token hashes to a digest that matches nothing.
      expect(described_class.find_by(token_digest: Digest::SHA256.hexdigest("nope"))).to be_nil
    end
  end

  # ---------------------------------------------------------------------------
  # Lifecycle / state edges — expiry boundary and the pending scope's exclusions.
  # ---------------------------------------------------------------------------
  describe "#expired?" do
    it "is false while expires_at is in the future" do
      invitation = build(:invitation, expires_at: 1.hour.from_now)
      expect(invitation.expired?).to be(false)
    end

    it "is true once expires_at has passed" do
      invitation = build(:invitation, expires_at: 1.second.ago)
      expect(invitation.expired?).to be(true)
    end

    it "treats the exact boundary as expired (no off-by-one grace)" do
      frozen = Time.current
      invitation = build(:invitation, expires_at: frozen)
      travel_to(frozen) { expect(invitation.expired?).to be(true) }
    end
  end

  describe ".pending scope" do
    it "includes a pending, unexpired invitation" do
      live = create(:invitation, organization: organization, invited_by: owner,
                                  status: "pending", expires_at: 1.day.from_now)
      expect(described_class.pending).to include(live)
    end

    it "excludes accepted, revoked, and expired invitations" do
      accepted = create(:invitation, :accepted, organization: organization, invited_by: owner)
      revoked  = create(:invitation, :revoked, organization: organization, invited_by: owner)
      expired  = create(:invitation, organization: organization, invited_by: owner,
                                     status: "pending", expires_at: 1.day.ago)

      result = described_class.pending
      expect(result).not_to include(accepted)
      expect(result).not_to include(revoked)
      expect(result).not_to include(expired) # status pending but past expiry
    end
  end

  # ---------------------------------------------------------------------------
  # Uniqueness — the partial-unique index enforces "at most one open invite per
  # email per org", while leaving the same email free to be invited elsewhere.
  # ---------------------------------------------------------------------------
  describe "partial-unique index on (organization_id, email) WHERE status = 'pending'" do
    it "rejects a second pending invite for the same email in the same org" do
      create(:invitation, organization: organization, invited_by: owner,
                          email: "sam@acme.com", status: "pending")

      dup = build(:invitation, organization: organization, invited_by: owner,
                              email: "sam@acme.com", status: "pending")

      # The DB constraint is the backstop even if a model validation is bypassed.
      expect { dup.save!(validate: false) }.to raise_error(ActiveRecord::RecordNotUnique)
    end

    it "matches the email case-insensitively (citext column)" do
      create(:invitation, organization: organization, invited_by: owner,
                          email: "sam@acme.com", status: "pending")

      dup = build(:invitation, organization: organization, invited_by: owner,
                              email: "SAM@ACME.COM", status: "pending")

      expect { dup.save!(validate: false) }.to raise_error(ActiveRecord::RecordNotUnique)
    end

    it "allows a new pending invite for the same email after the prior one is revoked" do
      first = create(:invitation, organization: organization, invited_by: owner,
                                  email: "sam@acme.com", status: "pending")
      first.update!(status: "revoked") # no longer pending → frees the partial index slot

      reinvite = build(:invitation, organization: organization, invited_by: owner,
                                    email: "sam@acme.com", status: "pending")
      expect { reinvite.save! }.not_to raise_error
    end

    it "allows the SAME email to hold a pending invite in two DIFFERENT organizations" do
      other_org   = create(:organization)
      other_owner = create(:member, :owner, organization: other_org)

      create(:invitation, organization: organization, invited_by: owner,
                          email: "sam@acme.com", status: "pending")

      cross_org = build(:invitation, organization: other_org, invited_by: other_owner,
                                    email: "sam@acme.com", status: "pending")
      expect { cross_org.save! }.not_to raise_error
    end
  end
end
