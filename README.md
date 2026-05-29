# Liar's Bar Bot

受 Liar's Bar 啟發的 Discord 群組骰牌遊戲機器人。

## 檔案結構

```
liarsbar-bot/
├── bot.py          # 主程式入口
├── cog.py          # Discord 指令與按鈕邏輯
├── game.py         # 遊戲核心邏輯與資料結構
├── formatter.py    # ANSI 顏色格式化
├── views.py        # Discord UI 按鈕元件
├── requirements.txt
└── .env            # 本機開發用（不要上傳 GitHub）
```

## 遊戲指令

| 指令 | 說明 |
|------|------|
| `/create` | 建立新房間 |
| `/stop` | 強制結束遊戲 |
| `/status` | 查看血量狀態 |

## 遊戲流程

1. `/create` 建立房間
2. 玩家點「加入遊戲」按鈕
3. 任意玩家點「開始遊戲」
4. 輪到的玩家選手牌 → 點確認 → 選聲稱牌面
5. 下一位玩家選擇「質疑」或「放行」
6. 最後存活者獲勝

## 環境變數

`.env` 檔案（本機用）：
```
DISCORD_TOKEN=你的Bot Token
```

Render 部署時在 Environment Variables 設定 `DISCORD_TOKEN`。

## 牌面規則

- 牌面：A、K、Q、J 各 8 張，共 32 張
- 每人起始 5 張手牌、5 滴血
- 說謊被抓 → 出牌者扣血
- 質疑失敗 → 質疑者扣血
- 每輪質疑後重新發牌
