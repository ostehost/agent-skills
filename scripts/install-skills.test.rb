#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "minitest/autorun"
require_relative "test_helper"

class InstallSkillsTest < Minitest::Test
  include ScriptTestRepo

  def test_force_skips_target_that_is_source
    build_script_repo("install-skills", skills: { "sample" => good_frontmatter("sample") }) do |dir|
      stdout, stderr, status = run_script(
        dir, "install-skills", "--target", File.join(dir, "skills"), "--force", "sample"
      )

      assert status.success?, stderr
      assert_includes stderr, "target is source, skipping"
      assert_empty stdout
      skill_md = File.join(dir, "skills", "sample", "SKILL.md")
      assert File.exist?(skill_md), "expected #{skill_md} to survive"
    end
  end

  def test_force_copy_replaces_existing_symlink
    build_script_repo("install-skills", skills: { "sample" => good_frontmatter("sample") }) do |dir|
      target_dir = File.join(dir, "target")
      FileUtils.mkdir_p(target_dir)
      FileUtils.ln_s(File.join(dir, "skills", "sample"), File.join(target_dir, "sample"))

      stdout, stderr, status = run_script(
        dir, "install-skills", "--target", target_dir, "--force", "--mode", "copy", "sample"
      )

      assert status.success?, stderr
      assert_includes stdout, "copy sample"
      refute File.symlink?(File.join(target_dir, "sample"))
      copied = File.join(target_dir, "sample", "SKILL.md")
      source = File.join(dir, "skills", "sample", "SKILL.md")
      assert File.exist?(copied), "expected copy at #{copied}"
      assert File.exist?(source), "expected source at #{source} to remain"
    end
  end

  def test_list_prints_available_skills_sorted
    skills = %w[charlie alpha bravo].to_h { |name| [name, good_frontmatter(name)] }
    build_script_repo("install-skills", skills: skills) do |dir|
      stdout, _stderr, status = run_script(dir, "install-skills", "--list")

      assert status.success?
      assert_equal %w[alpha bravo charlie], stdout.split("\n")
    end
  end

  def test_unknown_skill_fails
    build_script_repo("install-skills", skills: { "sample" => good_frontmatter("sample") }) do |dir|
      stdout, stderr, status = run_script(dir, "install-skills", "nope")

      refute status.success?
      assert_includes stderr, "unknown skill(s): nope"
      assert_empty stdout
    end
  end

  def test_dry_run_leaves_target_untouched
    build_script_repo("install-skills", skills: { "sample" => good_frontmatter("sample") }) do |dir|
      target_dir = File.join(dir, "target")
      stdout, _stderr, status = run_script(dir, "install-skills", "--target", target_dir, "--dry-run", "sample")

      assert status.success?
      assert_includes stdout, "would symlink sample"
      refute File.exist?(target_dir), "dry-run must not create the target directory"
    end
  end

  def test_default_skip_if_exists
    build_script_repo("install-skills", skills: { "sample" => good_frontmatter("sample") }) do |dir|
      target_dir = File.join(dir, "target")
      FileUtils.mkdir_p(File.join(target_dir, "sample"))
      original_marker = File.join(target_dir, "sample", "marker")
      File.write(original_marker, "keep me")

      stdout, stderr, status = run_script(dir, "install-skills", "--target", target_dir, "sample")

      assert status.success?, stderr
      assert_includes stderr, "exists, skipping"
      assert_empty stdout
      assert File.exist?(original_marker), "non-forced reinstall must not touch an existing target"
    end
  end

  def test_invalid_mode_fails
    build_script_repo("install-skills", skills: { "sample" => good_frontmatter("sample") }) do |dir|
      stdout, stderr, status = run_script(dir, "install-skills", "--mode", "bogus", "sample")

      refute status.success?
      assert_equal 2, status.exitstatus
      assert_includes stderr, "invalid --mode: bogus"
      assert_empty stdout
    end
  end
end
