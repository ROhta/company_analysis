import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { toOku, toOkuDecimal, calcPercent } from '../utils/formatters';
import { COLORS } from '../constants/colors';
import { MetricCard } from './MetricCard';
import { BreakdownPanel } from './BreakdownPanel';
import { PlTooltip } from './ChartTooltip';

/**
 * 損益計算書（P/L）セクション
 */
export const PLSection = ({ pl, plComparison, settings }) => {
  // チャートデータをメモ化
  const plData = useMemo(() => [
    { name: '売上高', value: pl.売上高.value, color: COLORS.pl.売上高 },
    { name: '売上総利益', value: pl.売上総利益.value, color: COLORS.pl.売上総利益 },
    { name: '営業利益', value: pl.営業利益.value, color: COLORS.pl.営業利益 },
    { name: '経常利益', value: pl.経常利益.value, color: COLORS.pl.経常利益 },
    { name: '当期純利益', value: pl.当期純利益.value, color: COLORS.pl.当期純利益 },
  ], [pl]);

  const grossProfitMargin = calcPercent(pl.売上総利益.value, pl.売上高.value);

  return (
    <div className="space-y-8">
      {/* メトリクスカード */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="売上高"
          value={toOku(pl.売上高.value)}
          borderColor="border-blue-500"
          textColor="text-blue-600"
          yoyChange={pl.売上高.yoyChange}
        />
        <MetricCard
          label="営業利益"
          value={toOku(pl.営業利益.value)}
          borderColor="border-purple-500"
          textColor="text-purple-600"
          yoyChange={pl.営業利益.yoyChange}
        />
        <MetricCard
          label="経常利益"
          value={toOkuDecimal(pl.経常利益.value)}
          borderColor="border-cyan-500"
          textColor="text-cyan-600"
          yoyChange={pl.経常利益.yoyChange}
        />
        <MetricCard
          label="当期純利益"
          value={toOku(pl.当期純利益.value)}
          borderColor="border-pink-500"
          textColor="text-pink-600"
          yoyChange={pl.当期純利益.yoyChange}
        />
      </div>

      {/* 損益構造チャート */}
      <div className="bg-white rounded-xl p-6 shadow-md">
        <h2 className="text-xl font-bold text-gray-800 mb-4">損益構造（億円）</h2>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={plData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis
              tickFormatter={(v) => `${(v/100).toFixed(0)}億`}
              domain={settings.domain}
              ticks={settings.ticks}
            />
            <Tooltip content={<PlTooltip />} />
            <Bar dataKey="value" radius={[8, 8, 0, 0]}>
              {plData.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 期間比較チャート */}
      {plComparison && plComparison.length > 0 && (
        <div className="bg-white rounded-xl p-6 shadow-md">
          <h2 className="text-xl font-bold text-gray-800 mb-4">{plComparison.length}期業績比較（億円）</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={plComparison}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" />
              <YAxis
                tickFormatter={(v) => `${(v/100).toFixed(0)}億`}
                domain={settings.domain}
                ticks={settings.ticks}
              />
              <Tooltip formatter={(v) => `${toOkuDecimal(v)}億円`} />
              <Legend />
              <Bar dataKey="売上高" fill={COLORS.pl.売上高} radius={[4, 4, 0, 0]} />
              <Bar dataKey="営業利益" fill={COLORS.pl.営業利益} radius={[4, 4, 0, 0]} />
              <Bar dataKey="当期純利益" fill={COLORS.pl.当期純利益} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 各項目の内訳 */}
      <div className="bg-white rounded-xl p-6 shadow-md">
        <h2 className="text-xl font-bold text-gray-800 mb-4">各項目の内訳</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <BreakdownPanel
            title={`売上高 ${toOku(pl.売上高.value)}億円`}
            bgColor="bg-blue-50"
            titleColor="text-blue-700"
            items={[
              { dotColor: 'bg-red-400', label: '売上原価', value: `${toOku(pl.売上原価.value)}億円`, percent: calcPercent(pl.売上原価.value, pl.売上高.value) },
              { dotColor: 'bg-green-500', label: '売上総利益', value: `${toOku(pl.売上総利益.value)}億円`, percent: grossProfitMargin },
            ]}
          />
          <BreakdownPanel
            title={`売上総利益 ${toOku(pl.売上総利益.value)}億円`}
            bgColor="bg-green-50"
            titleColor="text-green-700"
            items={[
              { dotColor: 'bg-orange-400', label: '販売費及び一般管理費', value: `${toOku(pl.販管費.value)}億円`, percent: calcPercent(pl.販管費.value, pl.売上総利益.value) },
              { dotColor: 'bg-purple-500', label: '営業利益', value: `${toOku(pl.営業利益.value)}億円`, percent: calcPercent(pl.営業利益.value, pl.売上総利益.value) },
            ]}
          />
          <BreakdownPanel
            title={`経常利益 ${toOkuDecimal(pl.経常利益.value)}億円`}
            bgColor="bg-cyan-50"
            titleColor="text-cyan-700"
            items={[
              { dotColor: 'bg-purple-500', label: '営業利益', value: `${toOku(pl.営業利益.value)}億円`, percent: calcPercent(pl.営業利益.value, pl.経常利益.value) },
              { dotColor: 'bg-cyan-400', label: '営業外損益', value: `${toOkuDecimal(pl.営業外損益.value)}億円`, percent: calcPercent(pl.営業外損益.value, pl.経常利益.value) },
            ]}
          />
          <BreakdownPanel
            title={`当期純利益 ${toOku(pl.当期純利益.value)}億円`}
            bgColor="bg-pink-50"
            titleColor="text-pink-700"
            items={[
              { dotColor: 'bg-cyan-500', label: '経常利益', value: `${toOkuDecimal(pl.経常利益.value)}億円` },
              { dotColor: 'bg-gray-400', label: '特別損益・法人税等', value: `${pl.特別損益等.value >= 0 ? '' : '▲'}${toOkuDecimal(Math.abs(pl.特別損益等.value))}億円` },
            ]}
          />
        </div>
      </div>
    </div>
  );
};
