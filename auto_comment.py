"""
ルールベース自動コメント生成
テクニカル状況・センチメントの要約文を生成する。
※ 投資助言ではない。参考情報として表示する。
"""


def generate(analysis: dict, sentiment: dict = None) -> str:
    """分析結果から日本語1〜2文のコメントを返す。空なら空文字。"""
    if not analysis:
        return ""

    signal = analysis.get("signal", "HOLD")
    rsi    = float(analysis.get("rsi",  50) or 50)
    cross  = analysis.get("cross", None)
    ma_s   = float(analysis.get("ma_short", 0) or 0)
    ma_l   = float(analysis.get("ma_long",  0) or 0)

    parts = []

    # RSI評価
    if rsi >= 75:
        parts.append(f"RSI{rsi:.0f}と強い買われすぎ水準")
    elif rsi >= 70:
        parts.append(f"RSI{rsi:.0f}で買われすぎ圏")
    elif rsi <= 25:
        parts.append(f"RSI{rsi:.0f}と強い売られすぎ水準")
    elif rsi <= 30:
        parts.append(f"RSI{rsi:.0f}で売られすぎ圏")
    else:
        parts.append(f"RSI{rsi:.0f}（中立圏）")

    # MAクロス・トレンド
    if cross == "golden":
        parts.append("ゴールデンクロス発生中")
    elif cross == "dead":
        parts.append("デッドクロス発生中")
    elif ma_s and ma_l:
        if ma_s > ma_l:
            parts.append("短期MA > 長期MA（上昇トレンド）")
        else:
            parts.append("短期MA < 長期MA（下降トレンド）")

    # センチメント（ニュース）
    if sentiment:
        score = float(sentiment.get("score", 0) or 0)
        label = sentiment.get("label", "") or ""
        if label and label not in ("N/A", "—"):
            if score >= 0.5:
                parts.append(f"ニュース強気（{label}）")
            elif score <= -0.5:
                parts.append(f"ニュース弱気（{label}）")

    if not parts:
        return ""

    signal_label = {"BUY": "買いシグナル", "SELL": "売りシグナル"}.get(signal, "様子見")
    body = "、".join(parts) + "。"
    return f"【{signal_label}】{body}（自動生成・参考情報）"
