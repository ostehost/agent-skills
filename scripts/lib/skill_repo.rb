# frozen_string_literal: true

# Shared skill discovery for scripts/install-skills and scripts/validate-skills, so
# the two scripts can never disagree on "which skills exist on disk".
module SkillRepo
  def self.root
    File.expand_path("../..", __dir__)
  end

  def self.skills_root(root = self.root)
    File.join(root, "skills")
  end

  # Skill names with a SKILL.md, sorted. A leading-dot directory is never a real
  # skill and Dir.glob's "*" already can't see one, so install-skills must not
  # install what validate-skills (the source of truth for repo well-formedness)
  # can't see either. Dir.glob returns [] for a missing skills/ dir rather than
  # raising, so callers get a readable "no skills found" path instead of a crash.
  def self.names(root = self.root)
    Dir.glob(File.join(skills_root(root), "*", "SKILL.md")).map { |path| File.basename(File.dirname(path)) }.sort
  end
end
