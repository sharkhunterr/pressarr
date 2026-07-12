#!/usr/bin/env node
/**
 * Flexible release script for Pressarr
 *
 * Features:
 * - Bump version using standard-version
 * - Push to GitLab and/or GitHub
 * - Create releases on GitLab and/or GitHub with content from GITHUB_RELEASES.md
 * - Deploy to Docker Hub (triggers CI)
 * - Support for dry-run mode
 *
 * Usage:
 *   npm run release              # Standard release (GitLab only)
 *   npm run release:github       # Release to both GitLab and GitHub
 *   npm run release:deploy       # Release and trigger Docker deploy
 *   npm run release:full         # Release to both + Docker deploy
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Parse command line arguments
const args = process.argv.slice(2);
const options = {
  github: args.includes('--github'),
  gitlab: !args.includes('--no-gitlab'),
  deploy: args.includes('--deploy'),
  dryRun: args.includes('--dry-run'),
  skipPush: args.includes('--skip-push'),
  skipRelease: args.includes('--skip-release'),
  releaseType: args.find(arg => ['patch', 'minor', 'major'].includes(arg)) || null,
};

// Get current git remote URLs
function getRemoteUrl(remote) {
  try {
    return execSync(`git remote get-url ${remote}`, { encoding: 'utf8' }).trim();
  } catch {
    return null;
  }
}

// Execute command with logging
function exec(command, description) {
  console.log(`\n📦 ${description}...`);
  if (options.dryRun) {
    console.log(`   [DRY RUN] ${command}`);
    return '';
  }
  try {
    return execSync(command, { encoding: 'utf8', stdio: 'inherit' });
  } catch (error) {
    console.error(`❌ Failed: ${description}`);
    process.exit(1);
  }
}

// Read release notes from GITHUB_RELEASES.md
function getLatestReleaseNotes() {
  const releasesFile = path.join(__dirname, '..', 'GITHUB_RELEASES.md');

  if (!fs.existsSync(releasesFile)) {
    console.warn('⚠️  GITHUB_RELEASES.md not found, release will have no description');
    return '';
  }

  const content = fs.readFileSync(releasesFile, 'utf8');

  // Extract the first release section (most recent)
  const releaseMatch = content.match(/##\s+\[?v?[\d.]+\]?[^\n]*\n([\s\S]*?)(?=\n##|\n---|\Z)/);

  if (releaseMatch) {
    return releaseMatch[0].trim();
  }

  return content.trim();
}

// Get current version from package.json
function getCurrentVersion() {
  const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  return pkg.version;
}

// Main release flow
async function main() {
  console.log('🚀 Pressarr Release Script\n');
  console.log('Options:', options);

  // Check git status
  try {
    const status = execSync('git status --porcelain', { encoding: 'utf8' });
    if (status && !options.dryRun) {
      console.error('❌ Working directory not clean. Commit or stash changes first.');
      process.exit(1);
    }
  } catch (error) {
    console.error('❌ Failed to check git status');
    process.exit(1);
  }

  // Get current branch
  const currentBranch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf8' }).trim();
  console.log(`\n📌 Current branch: ${currentBranch}`);

  // Check remotes
  const gitlabUrl = getRemoteUrl('origin');

  console.log(`\n🔗 Remotes:`);
  console.log(`   GitLab: ${gitlabUrl || 'not configured'}`);
  console.log(`   GitHub: will use GITHUB_TOKEN env var or gh CLI auth`);

  if (options.gitlab && !gitlabUrl) {
    console.error('❌ GitLab remote (origin) not configured');
    process.exit(1);
  }

  // Step 1: Run standard-version to bump version
  let versionCmd = 'npx standard-version';
  if (options.releaseType) {
    versionCmd += ` --release-as ${options.releaseType}`;
  }
  if (options.dryRun) {
    versionCmd += ' --dry-run';
  }

  exec(versionCmd, 'Bumping version with standard-version');

  if (options.dryRun) {
    console.log('\n✅ Dry run completed. No changes made.');
    return;
  }

  const newVersion = getCurrentVersion();
  const tag = `v${newVersion}`;
  console.log(`\n✨ New version: ${tag}`);

  // Step 2: Push to GitLab (GitHub push is handled by GitLab CI)
  if (!options.skipPush) {
    const pushOptions = options.deploy ? '-o ci.variable="DEPLOY=true"' : '';

    if (options.gitlab) {
      exec(
        `git push origin ${currentBranch} --follow-tags ${pushOptions}`,
        'Pushing to GitLab'
      );

      if (options.github) {
        console.log('\n💡 GitHub push will be handled by GitLab CI');
      }
    }
  }

  // Step 3: Create releases
  if (!options.skipRelease) {
    const releaseNotes = getLatestReleaseNotes();
    const releaseNotesFile = '/tmp/pressarr-release-notes.md';
    fs.writeFileSync(releaseNotesFile, releaseNotes);

    if (options.gitlab && gitlabUrl) {
      console.log('\n📋 Creating GitLab release...');
      try {
        // Check if glab is installed
        execSync('which glab', { stdio: 'ignore' });

        const glabCmd = `glab release create ${tag} --notes-file "${releaseNotesFile}" --name "Release ${tag}"`;
        exec(glabCmd, 'Creating GitLab release');
      } catch {
        console.warn('⚠️  glab CLI not found. Skipping GitLab release creation.');
        console.log('   Install with: brew install glab (macOS) or https://gitlab.com/gitlab-org/cli');
      }
    }

    if (options.github) {
      console.log('\n📋 Creating GitHub release...');

      // Check for GITHUB_TOKEN env var
      const githubToken = process.env.GITHUB_TOKEN;
      const githubRepo = process.env.GITHUB_REPO || 'sharkhunterr/pressarr';

      if (!githubToken) {
        console.warn('⚠️  GITHUB_TOKEN not found in environment variables.');
        console.log('   GitHub release will be created by GitLab CI');
      } else {
        try {
          // Check if gh is installed
          execSync('which gh', { stdio: 'ignore' });

          // Use gh CLI with token from env
          const ghCmd = `GH_TOKEN=${githubToken} gh release create ${tag} --repo ${githubRepo} --notes-file "${releaseNotesFile}" --title "Release ${tag}"`;
          exec(ghCmd, 'Creating GitHub release');
        } catch {
          console.warn('⚠️  gh CLI not found.');
          console.log('   GitHub release will be created by GitLab CI');
          console.log('   Install gh CLI: brew install gh (macOS) or https://cli.github.com/');
        }
      }
    }

    // Cleanup
    if (fs.existsSync(releaseNotesFile)) {
      fs.unlinkSync(releaseNotesFile);
    }
  }

  console.log('\n✅ Release completed successfully!');
  console.log(`\n📦 Version: ${tag}`);

  if (options.deploy) {
    console.log(`\n🐳 Docker deployment triggered via GitLab CI`);
    console.log(`   Check pipeline: ${gitlabUrl}/-/pipelines`);
  }
}

// Run
main().catch(error => {
  console.error('\n❌ Release failed:', error.message);
  process.exit(1);
});
