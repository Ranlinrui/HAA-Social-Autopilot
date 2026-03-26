// Tweet content generator - crypto/AI themed
const TweetGen = (() => {
  const tweets = [
    "Just deployed a new MEV bot on Arbitrum. First hour: +$2,400. The alpha is in the execution layer.",
    "$BTC breaking out of the 4h wedge. Volume confirming. Next stop: new ATH.",
    "Thread on how I built an AI agent that monitors 200+ wallets and auto-trades based on smart money flow.",
    "The merge between AI and DeFi is the biggest opportunity since DeFi Summer 2020. Here's why:",
    "My Claude-powered trading bot just hit 847 consecutive profitable trades. Not luck - pure math.",
    "Whale alert: 15,000 $ETH just moved from Binance to an unknown wallet. Something's brewing.",
    "Built a sentiment analysis pipeline that processes 50K tweets/hour. Edge is real.",
    "New strategy: using LLM to parse governance proposals and front-run the market reaction. +340% in 2 weeks.",
    "The $SOL ecosystem is about to explode. 3 catalysts nobody is talking about:",
    "Just open-sourced my prediction market bot. 94.7% win rate over 12,000 trades.",
    "AI agents are the new meta. If you're not building with Claude/GPT, you're already behind.",
    "Spotted unusual options activity on $NVDA. Last time this pattern appeared: +45% in 30 days.",
    "My automated KOL monitoring system caught this alpha 47 minutes before CT. Speed is everything.",
    "Breaking: Major protocol about to announce token migration. Smart money already positioning.",
    "The future of trading isn't human vs human. It's agent vs agent. Build your army.",
    "Backtested this strategy across 3 years of data. Sharpe ratio: 4.2. Max drawdown: 3.1%.",
    "New on-chain signal: exchange reserves hitting 5-year lows. Supply shock incoming.",
    "Just integrated real-time news parsing into my bot. Response time: 0.3 seconds from headline to trade.",
    "The alpha leak: top funds are using AI to analyze satellite imagery for commodity trading.",
    "My portfolio tracker shows +1,247% YTD. All automated. All verifiable on-chain."
  ];

  const replies = [
    "Great analysis! The on-chain data confirms this thesis. Watching closely.",
    "This is exactly what our AI model predicted 2 hours ago. Bullish.",
    "Solid thread. Adding to our monitoring watchlist now.",
    "The data doesn't lie. Our sentiment engine flagged this yesterday.",
    "Interesting perspective. Our quant model shows similar signals.",
    "Been tracking this pattern for weeks. The confluence is undeniable.",
    "Our AI agent detected the same anomaly. Positioning accordingly.",
    "This aligns with our macro thesis. Risk/reward is asymmetric here.",
    "Smart take. The market hasn't priced this in yet.",
    "Our automated system already flagged this. Alpha is in speed."
  ];

  function pick(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  function genTweet() { return pick(tweets); }
  function genReply() { return pick(replies); }

  function genTimestamp() {
    const now = new Date();
    const offset = Math.floor(Math.random() * 300);
    now.setSeconds(now.getSeconds() - offset);
    return now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function genMetrics() {
    return {
      likes: Math.floor(Math.random() * 500) + 10,
      retweets: Math.floor(Math.random() * 200) + 5,
      replies: Math.floor(Math.random() * 80) + 2,
      views: Math.floor(Math.random() * 50000) + 1000
    };
  }

  return { genTweet, genReply, genTimestamp, genMetrics };
})();
