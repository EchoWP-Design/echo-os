// Version und Build werden beim Bauen in GitHub Actions eingesetzt (--dart-define).
const appVersion = String.fromEnvironment('APP_VERSION', defaultValue: 'dev');
const appBuild = String.fromEnvironment('APP_BUILD', defaultValue: '0');
