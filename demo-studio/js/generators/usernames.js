// Username generator - crypto/AI style handles
const UsernameGen = (() => {
  const prefixes = [
    '0x_', 'defi_', 'alpha_', 'crypto_', 'web3_', 'nft_',
    'the_', 'ser_', '', '', '', ''
  ];
  const names = [
    'whale', 'degen', 'maxi', 'hunter', 'trader', 'builder',
    'dev', 'chad', 'anon', 'punk', 'ape', 'bull',
    'signal', 'gem', 'moon', 'rocket', 'diamond', 'wolf',
    'shark', 'eagle', 'phoenix', 'titan', 'nexus', 'flux'
  ];
  const suffixes = [
    '', '', '', '_eth', '_sol', '_btc', '.lens',
    '69', '420', '_xyz', '_ai', '_lab', '_dao'
  ];
  const displayPrefixes = [
    '', '', 'The ', 'Sir ', 'Dr. ', 'Captain '
  ];
  const displayNames = [
    'Alpha Hunter', 'DeFi Whale', 'Crypto Sage', 'Web3 Builder',
    'Token Trader', 'Chain Analyst', 'Block Explorer', 'Yield Farmer',
    'NFT Collector', 'DAO Governor', 'Smart Money', 'Degen King',
    'Moon Walker', 'Diamond Hands', 'Bull Runner', 'Signal Master',
    'AI Researcher', 'Quant Dev', 'Data Scientist', 'ML Engineer',
    'Neural Net', 'Deep Learner', 'GPT Whisperer', 'Prompt Engineer'
  ];

  function pick(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  function genHandle() {
    return '@' + pick(prefixes) + pick(names) + pick(suffixes);
  }

  function genDisplayName() {
    return pick(displayPrefixes) + pick(displayNames);
  }

  function genAvatar(name) {
    return name.charAt(0).toUpperCase();
  }

  return { genHandle, genDisplayName, genAvatar };
})();
