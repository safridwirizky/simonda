import React from 'react';
import { RingkasanStatistik, UserProfile } from '../types';
import {
  Trophy,
  AlertTriangle,
  CheckCircle2,
  Building2,
  Download,
  PlusCircle,
  FileCheck,
  Zap,
  Check,
  XCircle,
} from 'lucide-react';

interface DashboardViewProps {
  stats: RingkasanStatistik | null;
  user: UserProfile | null;
  onOpenNewInovasi: () => void;
  onNavigateTab: (tab: 'inovasi' | 'spd' | 'rekap') => void;
  onExportCsv: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  stats,
  user,
  onOpenNewInovasi,
  onNavigateTab,
  onExportCsv,
}) => {
  if (!stats) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  const p = stats.proyeksi_terverifikasi;
  const pKlaim = stats.proyeksi_klaim;
  const totalYandas = p.yandas_terisi.length + p.yandas_kosong.length;
  const minYandas = p.yandas_terpenuhi + p.yandas_kurang;

  const isSangatInovatif = p.indeks >= 65.01;
  const isInovatif = p.indeks >= 40.01 && p.indeks < 65.01;

  return (
    <div className="space-y-6">
      
      {/* Top Welcome Banner & Actions */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 rounded-2xl p-6 text-white shadow-xl border border-slate-800 relative overflow-hidden">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-64 h-64 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none"></div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center space-x-2 text-emerald-400 text-xs font-bold uppercase tracking-wider mb-2">
              <Zap className="w-4 h-4" />
              <span>Monitoring IGA Kemendagri &bull; Tahun {stats.tahun}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Proyeksi Indeks Inovasi Daerah Rote Ndao
            </h1>
            <p className="text-slate-300 text-sm mt-1 max-w-2xl">
              Sistem perhitungan otomatis Indeks Inovasi Daerah berbasis Peraturan Kepala BSKDN Kemendagri.
            </p>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={onOpenNewInovasi}
              className="flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm shadow-lg shadow-emerald-500/20 transition transform active:scale-95"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Buat Inovasi Baru</span>
            </button>

            {user?.bisa_verifikasi && (
              <button
                onClick={onExportCsv}
                className="flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-sm font-semibold transition"
              >
                <Download className="w-4 h-4 text-emerald-400" />
                <span>Ekspor CSV IGA</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Meter Score Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
                <Trophy className="w-5 h-5 text-amber-500" />
                <span>Indeks Inovasi Daerah Terverifikasi</span>
              </h2>
              <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md font-semibold">
                Skor Maks: 250
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 items-center my-2">
              
              {/* Big Score Meter */}
              <div className="bg-slate-50 rounded-xl p-5 border border-slate-100 text-center relative">
                <div className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">
                  Proyeksi Nilai Akhir
                </div>
                <div className="text-5xl font-black text-slate-900 tracking-tight">
                  {p.indeks.toFixed(2)}
                </div>
                <div className="text-xs text-slate-400 mt-1">Skor Total: {p.skor_total} / 250</div>

                <div className="mt-3 inline-block">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide ${
                      isSangatInovatif
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                        : isInovatif
                        ? 'bg-blue-100 text-blue-800 border border-blue-300'
                        : 'bg-amber-100 text-amber-800 border border-amber-300'
                    }`}
                  >
                    Kategori: {p.kategori}
                  </span>
                </div>
              </div>

              {/* Comparison & Claim Score */}
              <div className="space-y-3">
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="text-xs font-medium text-slate-500">Skor Klaim Mandiri OPD</div>
                  <div className="flex items-baseline space-x-2 mt-0.5">
                    <span className="text-2xl font-extrabold text-slate-700">{pKlaim.indeks.toFixed(2)}</span>
                    <span className="text-xs text-slate-500">({pKlaim.kategori})</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Sebelum verifikasi dan eliminasi inovasi yang belum layak.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-100">
                  <div className="text-xs font-semibold text-emerald-900">Persyaratan Minimal Pembagi</div>
                  <div className="text-xs text-emerald-700 mt-0.5">
                    Minimal {stats.proyeksi_terverifikasi.pembagi} inovasi agar skor rata-rata kematangan tidak terbagi oleh slot kosong.
                  </div>
                </div>
              </div>

            </div>
          </div>

          {/* Detailed Score Breakdown Row */}
          <div className="grid grid-cols-3 gap-3 pt-4 border-t border-slate-100 text-center text-xs mt-4">
            <div className="p-2.5 rounded-lg bg-slate-50">
              <span className="text-slate-500 font-medium block">SPD Daerah (15)</span>
              <span className="text-base font-bold text-slate-900">{p.skor_spd} / 63</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50">
              <span className="text-slate-500 font-medium block">Rata Kematangan</span>
              <span className="text-base font-bold text-slate-900">{p.rata_kematangan}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50">
              <span className="text-slate-500 font-medium block">Skor Jumlah Inovasi</span>
              <span className="text-base font-bold text-slate-900">{p.skor_jumlah_inovasi} / 76</span>
            </div>
          </div>

        </div>

        {/* Critical Criteria Warning Box */}
        <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-sm border border-slate-800 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-white flex items-center space-x-2 mb-3">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
              <span>Syarat Mutlak Lampiran I IGA</span>
            </h3>

            {/* Urusan Yandas Status */}
            <div className="mb-4 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-300 font-medium">Urusan Wajib Pelayanan Dasar</span>
                <span className={`font-bold ${p.yandas_kurang === 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {p.yandas_terpenuhi} dari {totalYandas} Terpenuhi
                </span>
              </div>

              {p.yandas_kurang > 0 ? (
                <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-xs text-amber-200">
                  <p className="font-semibold text-amber-300 mb-1">
                    &bull; Kurang {p.yandas_kurang} Urusan Pelayanan Dasar!
                  </p>
                  <p className="text-[11px] text-slate-300">
                    Bila &lt; {minYandas} urusan wajib, seluruh <b>76 poin (30.4%)</b> skor Jumlah Inovasi menjadi NOL.
                  </p>
                </div>
              ) : (
                <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-300 flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Sebaran {totalYandas} urusan wajib pelayanan dasar telah terpenuhi sempurna!</span>
                </div>
              )}
            </div>

            {/* Urusan Yandas Checklist */}
            <div className="space-y-1.5 text-xs">
              <span className="text-slate-400 font-semibold block text-[11px] uppercase tracking-wider">
                Checklist {totalYandas} Urusan Yandas:
              </span>
              <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                {p.yandas_terisi.map((u) => (
                  <div key={u} className="flex items-center space-x-1.5 text-emerald-300">
                    <Check className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                    <span className="truncate">{u}</span>
                  </div>
                ))}
                {p.yandas_kosong.map((u) => (
                  <div key={u} className="flex items-center space-x-1.5 text-slate-500 line-through">
                    <XCircle className="w-3.5 h-3.5 shrink-0 text-slate-600" />
                    <span className="truncate">{u}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 mt-4 flex items-center justify-between text-xs text-slate-400">
            <span>Slot Pembagi Kosong:</span>
            <span className="font-bold text-white">{p.kursi_kosong} Inovasi</span>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
            <FileCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-semibold">Total Inovasi</div>
            <div className="text-2xl font-extrabold text-slate-900">{stats.total_inovasi}</div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-lg">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-semibold">Terverifikasi</div>
            <div className="text-2xl font-extrabold text-emerald-600">{stats.terverifikasi}</div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="p-3 bg-purple-50 text-purple-600 rounded-lg">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-semibold">Memenuhi Syarat</div>
            <div className="text-2xl font-extrabold text-purple-600">{stats.layak}</div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-lg">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-500 font-semibold">OPD Lapor</div>
            <div className="text-2xl font-extrabold text-slate-900">{stats.opd_terlibat}</div>
          </div>
        </div>

      </div>

      {/* Breakdown Lists Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Tahapan Inovasi */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center justify-between">
            <span>Inovasi Menurut Tahapan</span>
            <button
              onClick={() => onNavigateTab('inovasi')}
              className="text-xs text-emerald-600 font-semibold hover:underline"
            >
              Lihat Semua &rarr;
            </button>
          </h3>
          <div className="space-y-3">
            {stats.per_tahapan.map((t) => {
              const pct = stats.total_inovasi ? Math.round((t.jumlah / stats.total_inovasi) * 100) : 0;
              return (
                <div key={t.label} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-700">{t.label}</span>
                    <span className="text-slate-900">{t.jumlah} ({pct}%)</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div
                      className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Bentuk Inovasi */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center justify-between">
            <span>Inovasi Menurut Bentuk</span>
            <button
              onClick={() => onNavigateTab('inovasi')}
              className="text-xs text-emerald-600 font-semibold hover:underline"
            >
              Lihat Semua &rarr;
            </button>
          </h3>
          <div className="space-y-3">
            {stats.per_bentuk.map((b) => {
              const pct = stats.total_inovasi ? Math.round((b.jumlah / stats.total_inovasi) * 100) : 0;
              return (
                <div key={b.label} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-700 truncate max-w-[220px]">{b.label}</span>
                    <span className="text-slate-900">{b.jumlah} ({pct}%)</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>

    </div>
  );
};
