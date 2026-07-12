#!/usr/bin/env node
/**
 * Flexible git push script for Pressarr
 *
 * Features:
 * - Push to GitLab and/or GitHub
 * - Control tag pushing
 * - Support for CI variables
 *
 * Usage:
 *   npm run push                 # Push to GitLab only
 *   npm run push:github          # Push to GitHub only
 *   npm run push:all             # Push to both GitLab and GitHub
 *   npm run push:tags            # Push only tags to configured remotes
 */

const { execSync } = require('child_process');

// Parse command line arguments
const args = process.argv.slice(2);
const options = {
  github: args.includes('--github'),
  gitlab: args.includes('--gitlab') || (!args.includes('--github') && !args.includes('--tags-only')),
  all: args.includes('--all'),
  tagsOnly: args.includes('--tags-only'),
  noTags: args.includes('--no-tags'),
  force: args.includes('--force'),
  dryRun: args.includes('--dry-run'),
};

// If --all, enable both
if (options.all) {
  options.github = true;
  options.gitlab = true;
}

// Get remote URL
function getRemoteUrl(remote) {
  try {
    return execSync(`git remote get-url ${remote}`, { encoding: 'utf8' }).trim();
  } catch {
    return null;
  }
}

// Execute command
function exec(command, description) {
  console.log(`\n📤 ${description}...`);
  if (options.dryRun) {
    console.log(`   [DRY RUN] ${command}`);
    return '';
  }
  try {
    const output = execSync(command, { encoding: 'utf8', stdio: 'inherit' });
    console.log('   ✅ Done');
    return output;
  } catch (error) {
    console.error(`   ❌ Failed: ${description}`);
    process.exit(1);
  }
}

function main() {
  console.log('🚀 Pressarr Push Script\n');
  console.log('Options:', options);

  // Get current branch
  const currentBranch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf8' }).trim();
  console.log(`\n📌 Current branch: ${currentBranch}`);

  // Check remotes
  const gitlabUrl = getRemoteUrl('origin');
  const githubUrl = getRemoteUrl('github');

  console.log(`\n🔗 Remotes:`);
  console.log(`   GitLab: ${gitlabUrl || 'not configured'}`);
  console.log(`   GitHub: ${githubUrl || 'not configured'}`);

  if (options.gitlab && !gitlabUrl) {
    console.error('❌ GitLab remote (origin) not configured');
    process.exit(1);
  }

  if (options.github && !githubUrl) {
    console.error('❌ GitHub remote not configured');
    console.log('\n💡 Add GitHub remote with: git remote add github <url>');
    process.exit(1);
  }

  // Build push command options
  let pushOpts = '';
  if (options.force) pushOpts += ' --force';

  if (options.tagsOnly) {
    // Push only tags
    if (options.gitlab) {
      exec(`git push origin --tags${pushOpts}`, 'Pushing tags to GitLab');
    }
    if (options.github) {
      exec(`git push github --tags${pushOpts}`, 'Pushing tags to GitHub');
    }
  } else {
    // Push branch (and optionally tags)
    if (!options.noTags) {
      pushOpts += ' --follow-tags';
    }

    if (options.gitlab) {
      exec(`git push origin ${currentBranch}${pushOpts}`, 'Pushing to GitLab');
    }

    if (options.github) {
      exec(`git push github ${currentBranch}${pushOpts}`, 'Pushing to GitHub');
    }
  }

  console.log('\n✅ Push completed successfully!');
}

// Run
main();
