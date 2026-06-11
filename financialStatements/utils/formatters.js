// 数値フォーマット用ユーティリティ関数

/**
 * 百万円単位の値を億円単位（整数）に変換
 * @param {number} value - 百万円単位の値
 * @returns {string} 億円単位の値（整数）
 */
export const toOku = (value) => (value / 100).toFixed(0);

/**
 * 百万円単位の値を億円単位（小数点1桁）に変換
 * @param {number} value - 百万円単位の値
 * @returns {string} 億円単位の値（小数点1桁）
 */
export const toOkuDecimal = (value) => (value / 100).toFixed(1);

/**
 * 百万円単位の値を符号付き億円単位（小数点1桁）に変換
 * 正値は「+」、負値は「▲」を付け、絶対値で表示する。
 * 増減額（IFRS企業の運転資本増減など正負どちらも取りうる項目）の表示に使う。
 * @param {number} value - 百万円単位の値
 * @returns {string} 例: "+1234.5" / "▲1838.7"
 */
export const toOkuSignedDecimal = (value) =>
  `${value >= 0 ? '+' : '▲'}${toOkuDecimal(Math.abs(value))}`;

/**
 * パーセンテージを計算
 * @param {number} part - 分子
 * @param {number} total - 分母
 * @returns {string} パーセンテージ（小数点1桁）
 */
export const calcPercent = (part, total) => ((part / total) * 100).toFixed(1);

/**
 * 前年同期比の表示用フォーマット判定
 * @param {string} yoyChange - 前年同期比の文字列
 * @returns {boolean} マイナスかどうか
 */
export const isNegativeChange = (yoyChange) =>
  yoyChange?.startsWith('▲') || yoyChange?.startsWith('-');
