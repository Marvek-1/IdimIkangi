import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { TrendingUp, TrendingDown, Percent, BarChart2, Award } from 'lucide-react';

interface PerformanceStatsProps {
  stats: any;
  theme: any;
}

const PerformanceStats: React.FC<PerformanceStatsProps> = ({ stats, theme }) => {
  // Mock data for preview if stats are missing
  const defaultStats = {
    total: { wins: 42, losses: 18, expired: 5, win_rate: 70, profit_factor: 2.33, total: 65 },
    simulated: { wins: 30, losses: 12, expired: 3, win_rate: 71.4, profit_factor: 2.5, total: 42 },
    live: { wins: 12, losses: 6, expired: 2, win_rate: 66.7, profit_factor: 2.0, total: 23 }
  };

  const activeStats = stats && stats.total ? stats : defaultStats;
  const totalStats = activeStats.total;

  const pieData = [
    { name: 'Wins', value: totalStats.wins, color: theme.signal.success },
    { name: 'Losses', value: totalStats.losses, color: theme.signal.danger },
    { name: 'Expired', value: totalStats.expired, color: 'rgba(255,255,255,0.2)' },
  ];

  const barData = [
    { name: 'Simulated', wins: activeStats.simulated.wins, losses: activeStats.simulated.losses },
    { name: 'Live', wins: activeStats.live.wins, losses: activeStats.live.losses },
  ];

  return (
    <div style={{ 
      background: theme.base.slate, 
      borderRadius: 16, 
      border: `1px solid ${theme.base.border}`,
      padding: 20,
      display: "flex",
      flexDirection: "column",
      gap: 16,
      height: "100%"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <BarChart2 size={14} color={theme.flow.primary} />
        <span style={{ fontSize: 10, fontWeight: 900, letterSpacing: 1, color: "rgba(255,255,255,0.4)" }}>PERFORMANCE ANALYTICS</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, flex: 1 }}>
        {/* Win/Loss Distribution */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontSize: 9, fontWeight: 800, color: "rgba(255,255,255,0.3)" }}>OUTCOME DISTRIBUTION</div>
          <div style={{ height: 120 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={30}
                  outerRadius={50}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ background: theme.base.slate, border: `1px solid ${theme.base.border}`, fontSize: 10 }}
                  itemStyle={{ color: '#fff' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", justifyContent: "space-around", fontSize: 10, fontWeight: 800 }}>
            <div style={{ color: theme.signal.success }}>W: {totalStats.wins}</div>
            <div style={{ color: theme.signal.danger }}>L: {totalStats.losses}</div>
            <div style={{ color: "rgba(255,255,255,0.4)" }}>E: {totalStats.expired}</div>
          </div>
        </div>

        {/* Key Metrics */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, justifyContent: "center" }}>
          <div style={{ 
            background: "rgba(0,0,0,0.2)", 
            padding: "10px 16px", 
            borderRadius: 12, 
            border: "1px solid rgba(255,255,255,0.03)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Percent size={14} color={theme.signal.success} />
              <span style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.5)" }}>WIN RATE</span>
            </div>
            <span style={{ fontSize: 16, fontWeight: 900, color: theme.signal.success, fontFamily: "monospace" }}>
              {totalStats.win_rate}%
            </span>
          </div>

          <div style={{ 
            background: "rgba(0,0,0,0.2)", 
            padding: "10px 16px", 
            borderRadius: 12, 
            border: "1px solid rgba(255,255,255,0.03)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <TrendingUp size={14} color={theme.flow.primary} />
              <span style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.5)" }}>PROFIT FACTOR</span>
            </div>
            <span style={{ fontSize: 16, fontWeight: 900, color: theme.fire.primary, fontFamily: "monospace" }}>
              {totalStats.profit_factor}
            </span>
          </div>

          <div style={{ 
            background: "rgba(0,0,0,0.2)", 
            padding: "10px 16px", 
            borderRadius: 12, 
            border: "1px solid rgba(255,255,255,0.03)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Award size={14} color={theme.signal.success} />
              <span style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.5)" }}>TOTAL TRADES</span>
            </div>
            <span style={{ fontSize: 16, fontWeight: 900, color: "#fff", fontFamily: "monospace" }}>
              {totalStats.total}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceStats;
