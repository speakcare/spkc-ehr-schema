// pack-extension.js
const fs = require('fs');
const path = require('path');
const execSync = require('child_process').execSync;

// Step 1: Update the version string
const packageJsonPath = path.join(__dirname, 'package.json');
const manifestJsonPath = path.join(__dirname, 'public', 'manifest.json');

function incrementVersion(filePath) {
  const fileContent = fs.readFileSync(filePath, 'utf8');
  const jsonContent = JSON.parse(fileContent);

  if (jsonContent.version) {
    const versionParts = jsonContent.version.split('.');
    versionParts[versionParts.length - 1] = (parseInt(versionParts[versionParts.length - 1]) + 1).toString();
    const newVersion = versionParts.join('.');
    jsonContent.version = newVersion;

    fs.writeFileSync(filePath, JSON.stringify(jsonContent, null, 2), 'utf8');
    return newVersion;
  } else {
    throw new Error(`No version field found in ${filePath}`);
  }
}

function updateVersion(jsonFilePath, versionString) {
  const fileContent = fs.readFileSync(jsonFilePath, 'utf8');
  const jsonContent = JSON.parse(fileContent);

  jsonContent.version = versionString;

  fs.writeFileSync(jsonFilePath, JSON.stringify(jsonContent, null, 2), 'utf8');
  return versionString;
}

console.log('Incrementing version in package.json...');
const newVersion = incrementVersion(packageJsonPath);
console.log(`New version: ${newVersion}`);

console.log(`Updating version ${newVersion} in manifest.json...`);
updateVersion(manifestJsonPath, newVersion);

// Step 2: Run yarn build:extension
console.log('Building the extension...');
execSync('yarn build', { stdio: 'inherit' });

// Step 3: Zip the build directory with the version in the filename
const zipFileName = `speakcare-lens-${newVersion}.zip`;
const zipCommand = `zip -r ${zipFileName} dist`;

console.log('Creating ZIP file...');
execSync(zipCommand, { stdio: 'inherit' });

// Step 4: Move the ZIP file to the "builds" directory
const buildsDir = path.join(__dirname, 'builds');
if (!fs.existsSync(buildsDir)) {
  fs.mkdirSync(buildsDir);
}

const zipFilePath = path.join(__dirname, zipFileName);
const targetZipFilePath = path.join(buildsDir, zipFileName);

console.log('Moving ZIP file to builds directory...');
fs.renameSync(zipFilePath, targetZipFilePath);

// Step 5: Git add and commit the new version and ZIP file
const gitAddCommand = `git add ${packageJsonPath} ${manifestJsonPath} ${targetZipFilePath}`;
const gitCommitCommand = `git commit -m "extension version ${newVersion}"`;

console.log('Adding updated files to git...');
execSync(gitAddCommand, { stdio: 'inherit' });

console.log('Committing new version...');
execSync(gitCommitCommand, { stdio: 'inherit' });

console.log(`pack-lens completed successfully for version ${newVersion}.`);
