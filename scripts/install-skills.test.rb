#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "minitest/autorun"
require "open3"
require "tmpdir"

class InstallSkillsTest < Minitest::Test
  def test_force_skips_target_that_is_source
    Dir.mktmpdir do |dir|
      FileUtils.mkdir_p(File.join(dir, "scripts"))
      FileUtils.mkdir_p(File.join(dir, "skills", "sample"))
      FileUtils.cp(File.join(__dir__, "install-skills"), File.join(dir, "scripts", "install-skills"))
      File.write(File.join(dir, "skills", "sample", "SKILL.md"), "---\nname: sample\ndescription: sample\n---\n")

      stdout, stderr, status = Open3.capture3(
        RbConfig.ruby,
        File.join(dir, "scripts", "install-skills"),
        "--target",
        File.join(dir, "skills"),
        "--force",
        "sample"
      )

      assert status.success?, stderr
      assert_includes stderr, "target is source, skipping"
      assert_empty stdout
      skill_md = File.join(dir, "skills", "sample", "SKILL.md")
      assert File.exist?(skill_md), "expected #{skill_md} to survive"
    end
  end

  def test_force_copy_replaces_existing_symlink
    Dir.mktmpdir do |dir|
      FileUtils.mkdir_p(File.join(dir, "repo", "scripts"))
      FileUtils.mkdir_p(File.join(dir, "repo", "skills", "sample"))
      FileUtils.mkdir_p(File.join(dir, "target"))
      FileUtils.cp(File.join(__dir__, "install-skills"), File.join(dir, "repo", "scripts", "install-skills"))
      File.write(File.join(dir, "repo", "skills", "sample", "SKILL.md"), "---\nname: sample\ndescription: sample\n---\n")
      FileUtils.ln_s(File.join(dir, "repo", "skills", "sample"), File.join(dir, "target", "sample"))

      stdout, stderr, status = Open3.capture3(
        RbConfig.ruby,
        File.join(dir, "repo", "scripts", "install-skills"),
        "--target",
        File.join(dir, "target"),
        "--force",
        "--mode",
        "copy",
        "sample"
      )

      assert status.success?, stderr
      assert_includes stdout, "copy sample"
      refute File.symlink?(File.join(dir, "target", "sample"))
      copied = File.join(dir, "target", "sample", "SKILL.md")
      source = File.join(dir, "repo", "skills", "sample", "SKILL.md")
      assert File.exist?(copied), "expected copy at #{copied}"
      assert File.exist?(source), "expected source at #{source} to remain"
    end
  end

  def test_list_prints_available_skills_sorted
    with_repo(%w[charlie alpha bravo]) do |scripts_dir|
      stdout, _stderr, status = Open3.capture3(RbConfig.ruby, File.join(scripts_dir, "install-skills"), "--list")

      assert status.success?
      assert_equal %w[alpha bravo charlie], stdout.split("\n")
    end
  end

  def test_unknown_skill_fails
    with_repo do |scripts_dir|
      stdout, stderr, status = Open3.capture3(RbConfig.ruby, File.join(scripts_dir, "install-skills"), "nope")

      refute status.success?
      assert_includes stderr, "unknown skill(s): nope"
      assert_empty stdout
    end
  end

  # Build a temp repo with install-skills and the named skills, yield its scripts dir.
  def with_repo(names = ["sample"])
    Dir.mktmpdir do |dir|
      FileUtils.mkdir_p(File.join(dir, "scripts"))
      FileUtils.cp(File.join(__dir__, "install-skills"), File.join(dir, "scripts", "install-skills"))
      names.each do |name|
        FileUtils.mkdir_p(File.join(dir, "skills", name))
        File.write(File.join(dir, "skills", name, "SKILL.md"), "---\nname: #{name}\ndescription: #{name}\n---\n")
      end
      yield File.join(dir, "scripts")
    end
  end
end
