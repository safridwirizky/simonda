import React, { useState } from 'react';
import { InovasiRingkas, OPD } from '../types';
import { KLASIFIKASI_KEMATANGAN } from '../api';
import { Search, Building2, ChevronRight, Gauge } from 'lucide-react';

interface MonitoringViewProps {
  inovasiList: InovasiRingkas[];
  opdList: OPD[];
  onSelectInovasi: (id: number) => void;
}

type Tier = 'danger' | 'warning' | 'hijau';

export const MonitoringView: React.FC<MonitoringViewProps> = ({
  inovasiList,
  opdList,
  onSelectInovasi,
}) => {
  const [tierFilter, setTierFilter] = useState<Tier | ''>('');
  const [opdFilter, setOpdFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');

  const jumlah: Record<Tier, number> = { danger: 0, warning: 0, hijau: 0 };
  for (const item of inovasiList) {
    jumlah[item.klasifikasi_kematangan] += 1;
  }

  const filteredList = inovasiList
    .filter((item) => (tierFilter ? item.klasifikasi_kematangan === tierFilter : true))
    .filter((item) => (opdFilter ? item.opd.id === Number(opdFilter) : true))
    .filter((item) =>
      searchTerm
        ? item.nama.toLowerCase().includes(searchTerm.toLowerCase()) ||
          item.opd.nama.toLowerCase().includes(searchTerm.toLowerCase())
        : true
    )
    .sort((a, b) => a.skor_klaim - b.skor_klaim);

  const tiers: Tier[] = ['danger', 'warning', 'hijau'];

  return (
    <div className="space-y-6">

      {/* Header */}
      <div>
        <div className="flex items-center space-x-2 text-xs font-bold text-emerald-600 mb-1 uppercase tracking-wider">
          <Gauge className="w-4 h-4" />
          <span>Monitoring Kematangan Inovasi</span>
        </div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
          Klasifikasi Kesiapan Inovasi
        </h1>
        <p className="text-sm text-slate-500 mt-1 max-w-2xl">
          Setiap inovasi dikelompokkan menurut skor klaim SID-nya sendiri (skala 0-111), supaya
          terlihat cepat inovasi mana yang masih perlu dikejar sebelum masa pelaporan ditutup.
          Klasifikasi ini terpisah dari status verifikasi dan syarat kelayakan resmi IGA.
        </p>
      </div>

      {/* Tier Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {tiers.map((tier) => {
          const meta = KLASIFIKASI_KEMATANGAN[tier];
          const active = tierFilter === tier;
          return (
            <button
              key={tier}
              onClick={() => setTierFilter(active ? '' : tier)}
              className={`text-left p-5 rounded-2xl border shadow-sm transition-all ${
                active
                  ? `${meta.solid} border-transparent shadow-md scale-[1.02]`
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className={`text-[11px] font-bold uppercase tracking-wider ${
                    active ? 'text-white/90' : 'text-slate-400'
                  }`}
                >
                  {meta.label}
                </span>
                <span className={`w-2.5 h-2.5 rounded-full ${active ? 'bg-white' : meta.dot}`} />
              </div>
              <div className={`text-3xl font-black ${active ? 'text-white' : 'text-slate-900'}`}>
                {jumlah[tier]}
              </div>
              <div className={`text-xs mt-1 ${active ? 'text-white/80' : 'text-slate-400'}`}>
                {meta.deskripsi} &bull; klik untuk {active ? 'batalkan filter' : 'saring'}
              </div>
            </button>
          );
        })}
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Cari nama inovasi / OPD..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <select
            value={opdFilter}
            onChange={(e) => setOpdFilter(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="">Semua OPD</option>
            {opdList.map((opd) => (
              <option key={opd.id} value={opd.id}>
                {opd.singkatan || opd.kode} - {opd.nama}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* List */}
      {filteredList.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 shadow-sm space-y-3">
          <Gauge className="w-10 h-10 text-slate-300 mx-auto" />
          <h3 className="text-base font-bold text-slate-800">Tidak ada inovasi ditemukan</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            Coba ubah kata kunci pencarian atau saringan OPD/klasifikasi.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm divide-y divide-slate-100">
          {filteredList.map((item) => {
            const meta = KLASIFIKASI_KEMATANGAN[item.klasifikasi_kematangan];
            return (
              <div
                key={item.id}
                onClick={() => onSelectInovasi(item.id)}
                className="p-4 flex items-center justify-between gap-4 hover:bg-slate-50 cursor-pointer transition group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${meta.dot}`} />
                  <div className="min-w-0">
                    <h3 className="text-sm font-bold text-slate-900 truncate group-hover:text-emerald-600 transition-colors">
                      {item.nama}
                    </h3>
                    <div className="flex items-center space-x-1.5 text-xs text-slate-500">
                      <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="truncate">{item.opd.nama}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-4 shrink-0">
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${meta.badge}`}>
                    {meta.label}
                  </span>
                  <div className="text-right w-20">
                    <div className="text-[11px] text-slate-400 font-medium">Skor Klaim</div>
                    <div className="text-sm font-extrabold text-slate-900">
                      {item.skor_klaim} <span className="text-xs text-slate-400 font-normal">/ 111</span>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
