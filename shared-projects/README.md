# Shared Projects

複数人で利用するChatGPT共有Project向けのGit正本namespaceです。

個人Projectの既存資産と共同Projectの資産を混在させず、共同Projectごとに独立したrootを持ちます。

## Active

- `hoshigaruna-katsitore/` — 「欲しがるな、勝ち取れ」3人共同の中央競馬予想・研究Project

各Projectの作業開始時は、そのProject rootの `README.md` と `.gpt/` 配下を確認してください。

既存の `horse-racing/` 等は別Projectの正本です。共有Projectから必要な機能を利用する場合も、無断で所有権を移したり複製正本を作ったりせず、明示的なinterface / adapterで接続します。
