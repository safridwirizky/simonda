import React, { useState } from 'react';
import { InovasiRingkas, OPD, UserProfile } from '../types';
import { KLASIFIKASI_KEMATANGAN } from '../api';
import { Search, Plus, Filter, AlertCircle, CheckCircle, Clock, Building2, ChevronRight, ShieldAlert } from 'lucide-react';

interface InovasiListViewProps {
  inovasiList: InovasiRingkas[];
  opdList: OPD[];
  user: UserProfile | null;
  onSelectInovasi: (id: number) => void;
  onOpenNewInovasi: () => void;
}

export const InovasiListView: React.FC<InovasiListViewProps> = ({
  inovasiList,
  opdList,
  user,
  onSelectInovasi,
  onOpenNewInovasi,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [tahapanFilter, setTahapanFilter] = useState<string>('');
  const [opdFilter, setOpdFilter] = useState<string>('');

  const filteredList = inovasiList.filter((item) => {
    const matchesSearch =
      item.nama.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.opd.nama.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.urusan.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter ? item.status === statusFilter : true;
    const matchesTahapan = tahapanFilter ? item.tahapan === tahapanFilter : true;
    const matchesOpd = opdFilter ? item.opd.id === Number(opdFilter) : true;

    return matchesSearch && matchesStatus && matchesTahapan && matchesOpd;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'terverifikasi':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Terverifikasi</span>
          </span>
        );
      case 'diajukan':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200">
            <Clock className="w-3.5 h-3.5" />
            <span>Menunggu Verifikasi</span>
          </span>
        );
      case 'revisi':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Perlu Revisi</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
            <span>Draft</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Header & New Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Daftar Inovasi Daerah</h1>
          <p className="text-sm text-slate-500">
            {filteredList.length} Inovasi terdaftar dalam sistem IGA Kemendagri Rote Ndao.
          </p>
        </div>

        <button
          onClick={onOpenNewInovasi}
          className="flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm shadow-md transition"
        >
          <Plus className="w-4 h-4" />
          <span>Buat Inovasi Baru</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          
          {/* Search Input */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Cari inovasi / OPD / urusan..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="">Semua Status</option>
              <option value="draft">Draft</option>
              <option value="diajukan">Menunggu Verifikasi</option>
              <option value="revisi">Perlu Revisi</option>
              <option value="terverifikasi">Terverifikasi</option>
            </select>
          </div>

          {/* Tahapan Filter */}
          <div>
            <select
              value={tahapanFilter}
              onChange={(e) => setTahapanFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="">Semua Tahapan</option>
              <option value="inisiatif">Inisiatif</option>
              <option value="uji_coba">Uji Coba</option>
              <option value="penerapan">Penerapan</option>
            </select>
          </div>

          {/* OPD Filter */}
          <div>
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
      </div>

      {/* Innovation Cards Grid */}
      {filteredList.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 shadow-sm space-y-3">
          <Filter className="w-10 h-10 text-slate-300 mx-auto" />
          <h3 className="text-base font-bold text-slate-800">Tidak ada inovasi ditemukan</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            Coba ubah kata kunci pencarian atau sesuaikan filter untuk melihat data yang diinginkan.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredList.map((item) => (
            <div
              key={item.id}
              onClick={() => onSelectInovasi(item.id)}
              className="bg-white rounded-2xl border border-slate-200 hover:border-emerald-500/50 hover:shadow-md transition-all duration-200 p-5 flex flex-col justify-between cursor-pointer group"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center space-x-1.5 text-xs text-slate-500 font-medium">
                    <Building2 className="w-3.5 h-3.5 text-slate-400" />
                    <span className="truncate max-w-[180px]">{item.opd.singkatan || item.opd.nama}</span>
                  </div>
                  {getStatusBadge(item.status)}
                </div>

                <h2 className="text-base font-bold text-slate-900 group-hover:text-emerald-600 transition-colors line-clamp-2 mb-2">
                  {item.nama}
                </h2>

                <div className="flex flex-wrap gap-1.5 mb-4 text-[11px]">
                  <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-medium">
                    {item.urusan || 'Urusan Umum'}
                  </span>
                  <span className="bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded font-medium capitalize">
                    {item.tahapan.replace('_', ' ')}
                  </span>
                  <span className="bg-blue-50 text-blue-800 px-2 py-0.5 rounded font-medium capitalize">
                    {item.jenis.replace('_', ' ')}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded font-bold border ${
                      KLASIFIKASI_KEMATANGAN[item.klasifikasi_kematangan].badge
                    }`}
                  >
                    {KLASIFIKASI_KEMATANGAN[item.klasifikasi_kematangan].label}
                  </span>
                </div>
              </div>

              {/* Bottom Scores & Eligibility */}
              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <div className="text-[11px] text-slate-400 font-medium">Skor Verifikasi</div>
                  <div className="text-sm font-extrabold text-slate-900">
                    {item.skor_terverifikasi} <span className="text-xs text-slate-400 font-normal">/ 111</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  {item.layak ? (
                    <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-1 rounded">
                      Layak IGA
                    </span>
                  ) : (
                    <span className="text-[11px] font-bold text-amber-700 bg-amber-50 px-2 py-1 rounded flex items-center space-x-1">
                      <ShieldAlert className="w-3 h-3 text-amber-500" />
                      <span>Belum Layak</span>
                    </span>
                  )}
                  <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};
