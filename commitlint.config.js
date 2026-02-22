module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'subject-min-length': [2, 'always', 15],
    'header-max-length': [2, 'always', 100],
    'scope-enum': [1, 'always', [
      'worker', 'lambdas', 'shared', 'frontend', 'infra', 'ci', 'docs', 'deps',
    ]],
  },
}
