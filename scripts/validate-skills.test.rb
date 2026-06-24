#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "json"
require "minitest/autorun"
require "open3"
require "tmpdir"

class ValidateSkillsTest < Minitest::Test
  # Build a throwaway repo with the validator copied in, the given skills written
  # as skills/<name>/SKILL.md, and an optional skills.sh.json manifest, then run it.
  def run_validate(skills:, manifest: nil)
    Dir.mktmpdir do |dir|
      FileUtils.mkdir_p(File.join(dir, "scripts"))
      FileUtils.cp(File.join(__dir__, "validate-skills"), File.join(dir, "scripts", "validate-skills"))

      skills.each do |name, frontmatter|
        skill_dir = File.join(dir, "skills", name)
        FileUtils.mkdir_p(skill_dir)
        File.write(File.join(skill_dir, "SKILL.md"), frontmatter)
      end
      File.write(File.join(dir, "skills.sh.json"), manifest) if manifest

      yield(*Open3.capture3(RbConfig.ruby, File.join(dir, "scripts", "validate-skills")))
    end
  end

  def good(name)
    "---\nname: #{name}\ndescription: does #{name} things\n---\n"
  end

  def grouping(*names)
    JSON.generate("groupings" => [{ "title" => "Group", "skills" => names }])
  end

  def test_valid_repo_passes
    run_validate(skills: { "alpha" => good("alpha") }, manifest: grouping("alpha")) do |stdout, _stderr, status|
      assert status.success?
      assert_includes stdout, "validated 1 skills"
      assert_includes stdout, "validated skills.sh.json"
    end
  end

  def test_missing_manifest_is_allowed
    run_validate(skills: { "alpha" => good("alpha") }) do |stdout, _stderr, status|
      assert status.success?
      refute_includes stdout, "skills.sh.json"
    end
  end

  def test_name_directory_mismatch_fails
    run_validate(skills: { "alpha" => good("beta") }) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "does not match directory"
    end
  end

  def test_missing_description_fails
    run_validate(skills: { "alpha" => "---\nname: alpha\n---\n" }) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "missing description"
    end
  end

  def test_manifest_dangling_reference_fails
    run_validate(skills: { "alpha" => good("alpha") }, manifest: grouping("alpha", "ghost")) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "unknown skill"
    end
  end

  def test_manifest_duplicate_skill_fails
    manifest = JSON.generate(
      "groupings" => [
        { "title" => "A", "skills" => ["alpha"] },
        { "title" => "B", "skills" => ["alpha"] }
      ]
    )
    run_validate(skills: { "alpha" => good("alpha") }, manifest: manifest) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "listed more than once"
    end
  end

  def test_manifest_duplicate_within_one_grouping_fails
    run_validate(skills: { "alpha" => good("alpha") }, manifest: grouping("alpha", "alpha")) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "listed more than once"
    end
  end

  def test_invalid_json_manifest_fails
    run_validate(skills: { "alpha" => good("alpha") }, manifest: "{ not json") do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "invalid JSON"
    end
  end

  # Valid JSON but the wrong shape must produce a readable error, never a backtrace.

  def test_manifest_top_level_array_fails
    run_validate(skills: { "alpha" => good("alpha") }, manifest: JSON.generate(["alpha"])) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "must be a JSON object"
      refute_includes stderr, "TypeError"
    end
  end

  def test_manifest_missing_groupings_fails
    run_validate(skills: { "alpha" => good("alpha") }, manifest: JSON.generate("grouping" => [])) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, 'missing "groupings"'
    end
  end

  def test_manifest_groupings_object_fails
    manifest = JSON.generate("groupings" => { "Review" => ["alpha"] })
    run_validate(skills: { "alpha" => good("alpha") }, manifest: manifest) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, '"groupings" must be an array'
      refute_includes stderr, "TypeError"
    end
  end

  def test_manifest_grouping_as_string_fails
    manifest = JSON.generate("groupings" => ["alpha"])
    run_validate(skills: { "alpha" => good("alpha") }, manifest: manifest) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "must be an object"
      refute_includes stderr, "TypeError"
    end
  end

  def test_manifest_non_string_skill_fails
    manifest = JSON.generate("groupings" => [{ "title" => "Group", "skills" => [nil] }])
    run_validate(skills: { "alpha" => good("alpha") }, manifest: manifest) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "non-string skill entry"
    end
  end

  def test_non_mapping_frontmatter_fails
    run_validate(skills: { "alpha" => "---\n- name: alpha\n---\n" }) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "frontmatter is not a mapping"
      refute_includes stderr, "TypeError"
    end
  end

  def test_empty_name_reports_once
    run_validate(skills: { "alpha" => "---\nname: \"\"\ndescription: x\n---\n" }) do |_stdout, stderr, status|
      refute status.success?
      assert_includes stderr, "missing name"
      refute_includes stderr, "does not match directory"
    end
  end
end
