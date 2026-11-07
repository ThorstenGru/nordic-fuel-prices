// Tests for the pure autocomplete functions in web/index.html (between AC-PURE-BEGIN and AC-PURE-END).  node tools/test_autocomplete.js
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const m = src.match(/\/\/ AC-PURE-BEGIN[^\n]*\n([\s\S]*?)\/\/ AC-PURE-END/); assert(m, 'pure block not found');
const { acNorm, acScore, acBuildCities, acBuildStations, acLocal, acMerge, acPhoton } = new Function(m[1] + '; return { acNorm, acScore, acBuildCities, acBuildStations, acLocal, acMerge, acPhoton };')();

// normalising: case, diacritics, ß/æ/ø/ł, punctuation
assert.strictEqual(acNorm('Göttingen'), 'gottingen'); assert.strictEqual(acNorm('Strasbourg'), 'strasbourg'); assert.strictEqual(acNorm('Malmö-Käglinge'), 'malmo kaglinge');
assert.strictEqual(acNorm('Straße'), 'strasse'); assert.strictEqual(acNorm('Århus Ø'), 'arhus o'); assert.strictEqual(acNorm(null), '');

// scoring: exact > prefix > word prefix > substring; every word must match
assert(acScore('malmo', 'malmo') > acScore('malmo', 'malmo city')); assert(acScore('malmo', 'malmo city') > acScore('malmo', 'north malmo'));
assert(acScore('malmo', 'north malmo') > acScore('malmo', 'xmalmox')); assert.strictEqual(acScore('malmo', 'lund'), 0);
assert(acScore('aral got', 'aral gottingen koenigsallee') > 0); assert.strictEqual(acScore('aral xyz', 'aral gottingen'), 0);

// index from station data
const data = {
  SE: [{ id: 'a', city: 'Malmö', lat: 55.6, lon: 13.0, name: 'Circle K Malmö' }, { id: 'b', city: 'Malmö', lat: 55.7, lon: 13.1, brand: 'OKQ8' }, { id: 'c', city: 'Malmslätt', lat: 58.4, lon: 15.5, name: 'Preem' }],
  DE: [{ id: 'd', city: 'Göttingen', lat: 51.5, lon: 9.9, name: 'ARAL', address: 'Königsallee 245' }, { id: 'e', city: '', lat: 1, lon: 1, name: 'No city' }, { id: 'f', city: 'X', name: 'no coords' }],
};
const cities = acBuildCities(data), stations = acBuildStations(data);
assert.strictEqual(cities.length, 3); const mal = cities.find(c => c.cc === 'SE' && c.name === 'Malmö');
assert.strictEqual(mal.n, 2); assert(Math.abs(mal.lat - 55.65) < 1e-9 && Math.abs(mal.lon - 13.05) < 1e-9);
assert.strictEqual(stations.length, 5);                       // only the station without coordinates is skipped; one without a name uses its brand

// local suggestions: towns first, bigger town first on equal prefix, stations after (3+ chars)
let r = acLocal('malm', cities, stations, 6);
assert.deepStrictEqual(r.filter(x => x.kind === 'city').map(x => x.name), ['Malmö', 'Malmslätt']);
r = acLocal('gott', cities, stations, 6); assert.strictEqual(r[0].kind, 'city'); assert(r.some(x => x.kind === 'station' && x.id === 'd'));
assert.deepStrictEqual(acLocal('g', cities, stations, 6), []);                         // too short
assert(acLocal('aral gott', cities, stations, 6).some(x => x.id === 'd'));             // station by brand + town
assert.strictEqual(acLocal('zzzz', cities, stations, 6).length, 0);
assert(acLocal('malm', cities, stations, 2).length <= 2);

// remote merge: towns we already have are not repeated, addresses are appended, cap respected
const local = acLocal('malm', cities, stations, 6);
const remote = [{ kind: 'addr', place: true, name: 'Malmö', cc: 'SE', lat: 55.6, lon: 13 }, { kind: 'addr', place: false, name: 'Malmövägen 3', cc: 'SE', lat: 1, lon: 1 }];
const mg = acMerge(local, remote, 8); assert(!mg.some(x => x.kind === 'addr' && x.name === 'Malmö')); assert(mg.some(x => x.name === 'Malmövägen 3'));
const dup = { kind: 'addr', place: true, name: 'Strasbourg', sub: 'Bas-Rhin, France', cc: 'FR', lat: 48.6, lon: 7.7 };
assert.strictEqual(acMerge([], [dup, { ...dup }], 8).length, 1);   // the same place twice from Photon shows once
assert(acMerge(local, remote, 2).length === 2); assert.deepStrictEqual(acMerge(local, null, 8), local);

// Photon features
const f = { properties: { name: 'Aral', street: 'Königsallee', housenumber: '245', city: 'Göttingen', country: 'Germany', countrycode: 'de', type: 'house' }, geometry: { coordinates: [9.93, 51.53] } };
const a = acPhoton(f); assert.strictEqual(a.kind, 'addr'); assert.strictEqual(a.cc, 'DE'); assert.strictEqual(a.lat, 51.53); assert.strictEqual(a.lon, 9.93); assert(a.sub.includes('Königsallee 245'));
assert.strictEqual(acPhoton({ properties: { name: 'X' }, geometry: { coordinates: ['a', 1] } }), null); assert.strictEqual(acPhoton({ properties: {}, geometry: { coordinates: [1, 2] } }), null); assert.strictEqual(acPhoton(null), null);
assert.strictEqual(acPhoton({ properties: { name: 'Göttingen', type: 'city', country: 'Germany', countrycode: 'DE' }, geometry: { coordinates: [9.9, 51.5] } }).place, true);
console.log('test_autocomplete: all passed');
