// C18: run with `node tests/test_leaderboard_client.cjs` from the repository root.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = { document: { addEventListener() {} }, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync('idfinder/static/leaderboard.js', 'utf8') +
  '\nthis.LeaderboardForTest = Leaderboard;', context);
const board = Object.create(context.LeaderboardForTest.prototype);
board.data = { components: ['rating', 'sentiment', 'interest', 'reliability', 'experience'] };
board.weights = Object.fromEntries(board.data.components.map(c => [c, 0]));
const row = { components: { rating: .9, sentiment: .6, interest: .5, reliability: .7, experience: .2 } };
assert.equal(board.score(row), 68.5);
board.weights = { rating: 0, sentiment: 0, interest: 0, reliability: 0, experience: 100 };
assert.equal(board.score(row), 20);
board.weights = Object.fromEntries(board.data.components.map(c => [c, 1e308]));
assert.equal(board.score(row), 68.5);
console.log('Passed: zero-weight fallback, custom weights and extreme-weight fallback.');
