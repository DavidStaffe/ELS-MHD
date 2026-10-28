// React Router uses TextEncoder, which CRA's jsdom does not supply.
const { TextEncoder, TextDecoder } = require('util');
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;
