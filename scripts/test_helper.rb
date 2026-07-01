# frozen_string_literal: true

require "fileutils"
require "open3"
require "tmpdir"

# Shared fixture builder for scripts/*.test.rb: a throwaway repo skeleton with one
# script under test (plus its scripts/lib/ dependencies) and zero or more
# skills/<name>/SKILL.md fixtures.
module ScriptTestRepo
  SCRIPTS_DIR = File.expand_path(__dir__)

  # Copies `script` (and scripts/lib/, if present) into a tmp repo, writes any given
  # skills/<name>/SKILL.md fixtures and an optional skills.sh.json manifest, then
  # yields the repo root. Callers needing extra fixtures (a pre-seeded target dir,
  # an existing symlink) can set those up inside the block before calling run_script.
  def build_script_repo(script, skills: {}, manifest: nil)
    Dir.mktmpdir do |dir|
      scripts_dir = File.join(dir, "scripts")
      FileUtils.mkdir_p(scripts_dir)
      FileUtils.cp(File.join(SCRIPTS_DIR, script), File.join(scripts_dir, script))
      lib_dir = File.join(SCRIPTS_DIR, "lib")
      FileUtils.cp_r(lib_dir, scripts_dir) if File.directory?(lib_dir)

      skills.each do |name, frontmatter|
        skill_dir = File.join(dir, "skills", name)
        FileUtils.mkdir_p(skill_dir)
        File.write(File.join(skill_dir, "SKILL.md"), frontmatter)
      end
      File.write(File.join(dir, "skills.sh.json"), manifest) if manifest

      yield dir
    end
  end

  # Runs `script` (already copied into dir/scripts by build_script_repo) with args,
  # returning [stdout, stderr, status].
  def run_script(dir, script, *args)
    Open3.capture3(RbConfig.ruby, File.join(dir, "scripts", script), *args)
  end

  def good_frontmatter(name)
    "---\nname: #{name}\ndescription: does #{name} things\n---\n"
  end
end
