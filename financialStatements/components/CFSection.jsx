import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell, ComposedChart, Line, ReferenceLine } from 'recharts';
import { toOku, toOkuDecimal, toOkuSignedDecimal } from '../utils/formatters';
import { COLORS } from '../constants/colors';
import { MetricCard } from './MetricCard';
import { BreakdownPanel } from './BreakdownPanel';
import { CfTooltip } from './ChartTooltip';

/**
 * キャッシュフロー計算書（C/F）セクション
 */
export const CFSection = ({ cf, cfComparison, settings, getComment }) => {
  // 棒グラフ用データをメモ化
  const cfBarData = useMemo(() => [
    { name: '営業CF', value: cf.営業CF.value, color: COLORS.cf.営業CF },
    { name: '投資CF', value: cf.投資CF.value, color: COLORS.cf.投資CF },
    { name: '財務CF', value: cf.財務CF.value, color: COLORS.cf.財務CF },
  ], [cf]);

  // ウォーターフォールチャート用データをメモ化
  const cfWaterfallData = useMemo(() => [
    { name: '期首現金', value: cf.期首現金残高.value, fill: COLORS.cf.期首現金 },
    { name: '営業CF', value: cf.営業CF.value, fill: COLORS.cf.営業CF },
    { name: '投資CF', value: cf.投資CF.value, fill: COLORS.cf.投資CF },
    { name: '財務CF', value: cf.財務CF.value, fill: COLORS.cf.財務CF },
    { name: '期末現金', value: cf.期末現金残高.value, fill: COLORS.cf.期末現金 },
  ], [cf]);

  // 現金増減額
  const cashChange = cf.期末現金残高.value - cf.期首現金残高.value;

  return (
    <div className="space-y-8">
      {/* メトリクスカード */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="営業CF"
          value={toOkuDecimal(cf.営業CF.value)}
          borderColor="border-green-500"
          textColor="text-green-600"
          yoyChange={cf.営業CF.yoyChange}
        />
        <MetricCard
          label="投資CF"
          value={`${cf.投資CF.value >= 0 ? '' : '▲'}${toOkuDecimal(Math.abs(cf.投資CF.value))}`}
          borderColor="border-red-500"
          textColor="text-red-600"
          yoyChange={cf.投資CF.yoyChange}
        />
        <MetricCard
          label="財務CF"
          value={`${cf.財務CF.value >= 0 ? '' : '▲'}${toOkuDecimal(Math.abs(cf.財務CF.value))}`}
          borderColor="border-orange-500"
          textColor="text-orange-600"
          yoyChange={cf.財務CF.yoyChange}
        />
        <MetricCard
          label="フリーCF"
          value={`${cf.フリーCF.value >= 0 ? '' : '▲'}${toOkuDecimal(Math.abs(cf.フリーCF.value))}`}
          borderColor="border-purple-500"
          textColor={cf.フリーCF.value >= 0 ? 'text-purple-600' : 'text-red-600'}
        />
      </div>

      {/* C/F構成チャート */}
      <div className="bg-white rounded-xl p-6 shadow-md">
        <h2 className="text-xl font-bold text-gray-800 mb-4">キャッシュフロー構成（億円）</h2>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={cfBarData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis
              tickFormatter={(v) => `${(v/100).toFixed(0)}億`}
              domain={settings.composition.domain}
              ticks={settings.composition.ticks}
            />
            <Tooltip content={<CfTooltip />} />
            <ReferenceLine y={0} stroke="#374151" strokeWidth={1} />
            <ReferenceLine
              y={cf.フリーCF.value}
              stroke={COLORS.cf.フリーCF}
              strokeWidth={3}
              strokeDasharray="8 4"
              label={{
                value: `フリーCF: ${toOkuDecimal(cf.フリーCF.value)}億円`,
                position: 'right',
                fill: COLORS.cf.フリーCF,
                fontSize: 12,
                fontWeight: 'bold'
              }}
            />
            <Bar dataKey="value" radius={[8, 8, 0, 0]}>
              {cfBarData.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="flex justify-center gap-6 mt-4">
          <div className="flex items-center gap-2"><span className="w-3 h-3 bg-green-500 rounded"></span><span className="text-sm">営業CF</span></div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 bg-red-500 rounded"></span><span className="text-sm">投資CF</span></div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 bg-orange-500 rounded"></span><span className="text-sm">財務CF</span></div>
          <div className="flex items-center gap-2"><span className="w-6 h-0.5 bg-purple-500" style={{ borderTop: '3px dashed #8b5cf6' }}></span><span className="text-sm">フリーCF（営業CF+投資CF）</span></div>
        </div>
      </div>

      {/* 現金増減フローチャート */}
      <div className="bg-white rounded-xl p-6 shadow-md">
        <h2 className="text-xl font-bold text-gray-800 mb-4">現金増減フロー（億円）</h2>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={cfWaterfallData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis
              tickFormatter={(v) => `${(v/100).toFixed(0)}億`}
              domain={settings.waterfall.domain}
              ticks={settings.waterfall.ticks}
            />
            <Tooltip
              formatter={(v) => [`${toOkuDecimal(v)}億円`, '金額']}
              labelStyle={{ fontWeight: 'bold' }}
            />
            <ReferenceLine y={0} stroke="#374151" strokeWidth={2} />
            <Bar dataKey="value" radius={[4, 4, 4, 4]}>
              {cfWaterfallData.map((entry, index) => (
                <Cell key={index} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        <div className="text-center text-gray-500 text-sm mt-4 p-3 bg-gray-50 rounded-lg">
          <span className="font-semibold">現金増減:</span> {cashChange >= 0 ? '+' : ''}{toOkuDecimal(cashChange)}億円
          <span className="mx-2">|</span>
          <span className="text-green-600">営業CF {toOkuDecimal(cf.営業CF.value)}億</span>
          <span className="mx-1">+</span>
          <span className="text-red-600">投資CF {toOkuDecimal(cf.投資CF.value)}億</span>
          <span className="mx-1">+</span>
          <span className="text-orange-600">財務CF {toOkuDecimal(cf.財務CF.value)}億</span>
          <span className="mx-1">=</span>
          <span className="font-bold">{toOkuDecimal(cf.営業CF.value + cf.投資CF.value + cf.財務CF.value)}億</span>
        </div>
      </div>

      {/* 期間比較チャート */}
      {cfComparison && cfComparison.length > 0 && (
        <div className="bg-white rounded-xl p-6 shadow-md">
          <h2 className="text-xl font-bold text-gray-800 mb-4">{cfComparison.length}期キャッシュフロー比較（億円）</h2>
          <ResponsiveContainer width="100%" height={350}>
            <ComposedChart data={cfComparison}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" />
              <YAxis
                tickFormatter={(v) => `${(v/100).toFixed(0)}億`}
                domain={settings.comparison.domain}
                ticks={settings.comparison.ticks}
              />
              <Tooltip formatter={(v) => `${toOkuDecimal(v)}億円`} />
              <Legend />
              <ReferenceLine y={0} stroke="#374151" strokeWidth={1} />
              <Bar dataKey="営業CF" fill={COLORS.cf.営業CF} radius={[4, 4, 0, 0]} />
              <Bar dataKey="投資CF" fill={COLORS.cf.投資CF} radius={[4, 4, 0, 0]} />
              <Bar dataKey="財務CF" fill={COLORS.cf.財務CF} radius={[4, 4, 0, 0]} />
              <Line type="monotone" dataKey="フリーCF" stroke={COLORS.cf.フリーCF} strokeWidth={3} strokeDasharray="8 4" dot={{ fill: COLORS.cf.フリーCF, strokeWidth: 2, r: 6 }} />
              <Line type="monotone" dataKey="期末現金" stroke={COLORS.cf.期末現金} strokeWidth={3} dot={{ fill: COLORS.cf.期末現金, strokeWidth: 2, r: 6 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* C/F内訳 */}
      <div className="bg-white rounded-xl p-6 shadow-md">
        <h2 className="text-xl font-bold text-gray-800 mb-4">キャッシュフロー内訳</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <BreakdownPanel
            title={`営業CF ${toOkuDecimal(cf.営業CF.value)}億円`}
            bgColor="bg-green-50"
            titleColor="text-green-700"
            items={[
              { dotColor: 'bg-green-500', label: '税前利益', value: `${toOku(cf.details.営業CF.税前利益)}億円` },
              { dotColor: 'bg-green-400', label: '減価償却費', value: `+${toOku(cf.details.営業CF.減価償却費)}億円` },
              { dotColor: 'bg-green-300', label: '運転資本増減等', value: `${toOkuSignedDecimal(cf.details.営業CF.運転資本増減)}億円` },
            ]}
            comment={getComment('cf', 'operating')}
            commentBorderColor="border-green-200"
            commentTextColor="text-green-700"
          />
          <BreakdownPanel
            title={`投資CF ${toOkuDecimal(cf.投資CF.value)}億円`}
            bgColor="bg-red-50"
            titleColor="text-red-700"
            items={[
              { dotColor: 'bg-red-500', label: '子会社株式取得', value: `${toOkuDecimal(cf.details.投資CF.子会社株式取得)}億円` },
              { dotColor: 'bg-red-400', label: '有形固定資産取得', value: `${toOkuDecimal(cf.details.投資CF.有形固定資産取得)}億円` },
            ]}
            comment={getComment('cf', 'investing')}
            commentBorderColor="border-red-200"
            commentTextColor="text-red-700"
          />
          <BreakdownPanel
            title={`財務CF ${toOkuDecimal(cf.財務CF.value)}億円`}
            bgColor="bg-orange-50"
            titleColor="text-orange-700"
            items={[
              { dotColor: 'bg-orange-500', label: '配当金支払', value: `${toOkuDecimal(cf.details.財務CF.配当金支払)}億円` },
              { dotColor: 'bg-orange-400', label: 'その他', value: `${toOkuDecimal(cf.details.財務CF.その他)}億円` },
            ]}
            comment={getComment('cf', 'financing')}
            commentBorderColor="border-orange-200"
            commentTextColor="text-orange-700"
          />
        </div>
      </div>
    </div>
  );
};
