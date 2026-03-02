/**
 * Custom version updater for Python version.py file
 * Used by standard-version to bump version in backend/app/version.py
 */

const versionRegex = /__version__\s*=\s*["']([^"']+)["']/;

module.exports.readVersion = function (contents) {
  const match = contents.match(versionRegex);
  if (match) {
    return match[1];
  }
  throw new Error('Could not find __version__ in version.py');
};

module.exports.writeVersion = function (contents, version) {
  return contents.replace(versionRegex, `__version__ = "${version}"`);
};
