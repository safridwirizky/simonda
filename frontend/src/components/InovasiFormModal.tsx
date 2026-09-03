import React, { useState } from 'react';
import { InovasiDetail, OPD, UserProfile } from '../types';
import { URUSAN } from '../api';
import { X, Save } from 'lucide-react';

interface InovasiFormModalProps {
  initialData?: InovasiDetail | null;
  opdList: OPD[];
  user: UserProfile | null;
  onClose: () => void;
  onSave: (data: any) => Promise<void>;
}

export const InovasiFormModal: React.FC<InovasiFormModalProps> = ({
  initialData,
  opdList,
  user,
  onClose,
  onSave,
}) => {
  const [opdId, setOpdId] = useState<number>(
    initialData?.opd?.id || user?.opd?.id || (opdList[0] ? opdList[0].id : 1)
  );
  const [nama, setNama] = useState(initialData?.nama || '');
  const [tahapan, setTahapan] = useState(initialData?.tahapan || 'penerapan');
  const [inisiator, setInisiator] = useState(initialData?.inisiator || 'perangkat_daerah');
  const [namaInisiator, setNamaInisiator] = useState(initialData?.nama_inisiator || '');
  const [klasifikasi, setKlasifikasi] = useState(initialData?.klasifikasi || 'perangkat_daerah');
  const [jenis, setJenis] = useState(initialData?.jenis || 'non_digital');
  const [bentuk, setBentuk] = useState(initialData?.bentuk || 'pelayanan_publik');
  const [urusan, setUrusan] = useState(initialData?.urusan || URUSAN[0]);
  const [mulaiUjiCoba, setMulaiUjiCoba] = useState(initialData?.mulai_uji_coba || '');
  const [mulaiPenerapan, setMulaiPenerapan] = useState(initialData?.mulai_penerapan || '');
  const [rancangBangun, setRancangBangun] = useState(initialData?.rancang_bangun || '');
  const [tujuan, setTujuan] = useState(initialData?.tujuan || '');
  const [manfaat, setManfaat] = useState(initialData?.manfaat || '');
  const [hasil, setHasil] = useState(initialData?.hasil || '');
  const [anggaran, setAnggaran] = useState<number | ''>(initialData?.anggaran || '');
  const [sumberAnggaran, setSumberAnggaran] = useState(initialData?.sumber_anggaran || '');
  const [picNama, setPicNama] = useState(initialData?.pic_nama || '');
  const [picKontak, setPicKontak] = useState(initialData?.pic_kontak || '');

  const [saving, setSaving] = useState(false);

  const kataCount = rancangBangun.trim() ? rancangBangun.trim().split(/\s+/).length : 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nama.trim()) {
      alert('Nama inovasi wajib diisi.');
      return;
    }
    if (!tujuan.trim()) {
      alert('Tujuan inovasi wajib diisi.');
      return;
    }

    setSaving(true);
    try {
      await onSave({
        opd_id: opdId,
        nama,
        tahapan,
        inisiator,
        nama_inisiator: namaInisiator,
        klasifikasi,
        jenis,
        bentuk,
        urusan,
        mulai_uji_coba: mulaiUjiCoba || null,
        mulai_penerapan: mulaiPenerapan || null,
        rancang_bangun: rancangBangun,
        tujuan,
        manfaat,
        hasil,
        anggaran: anggaran ? Number(anggaran) : null,
        sumber_anggaran: sumberAnggaran,
        pic_nama: picNama,
        pic_kontak: picKontak,
      });
      onClose();
    } catch (err: any) {
      alert(err.message || 'Gagal menyimpan data inovasi.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl border border-slate-200">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-3 mb-5">
          <h2 className="text-lg font-bold text-slate-900">
            {initialData ? 'Ubah Data Inovasi' : 'Tambah Inovasi Baru'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          
          {/* OPD Selector (for Admin/Verifikator) */}
          {user?.bisa_verifikasi && (
            <div>
              <label className="block font-bold text-slate-700 mb-1">OPD Pelaksana *</label>
              <select
                value={opdId}
                onChange={(e) => setOpdId(Number(e.target.value))}
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500"
              >
                {opdList.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.singkatan || o.kode} - {o.nama}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Nama Inovasi */}
          <div>
            <label className="block font-bold text-slate-700 mb-1">Nama Inovasi *</label>
            <input
              type="text"
              placeholder="Contoh: LONTAR - Layanan Online Otomasi Perpustakaan Sekolah"
              value={nama}
              onChange={(e) => setNama(e.target.value)}
              className="w-full p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500 text-sm font-semibold"
              required
            />
          </div>

          {/* Grid 1: Urusan, Tahapan, Jenis, Bentuk */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Urusan Utama *</label>
              <select
                value={urusan}
                onChange={(e) => setUrusan(e.target.value)}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl"
              >
                {URUSAN.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Tahapan *</label>
              <select
                value={tahapan}
                onChange={(e) => setTahapan(e.target.value as any)}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl"
              >
                <option value="inisiatif">Inisiatif</option>
                <option value="uji_coba">Uji Coba</option>
                <option value="penerapan">Penerapan</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Jenis Inovasi *</label>
              <select
                value={jenis}
                onChange={(e) => setJenis(e.target.value as any)}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl"
              >
                <option value="digital">Digital</option>
                <option value="non_digital">Non-Digital</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Bentuk Inovasi *</label>
              <select
                value={bentuk}
                onChange={(e) => setBentuk(e.target.value as any)}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl"
              >
                <option value="pelayanan_publik">Pelayanan Publik</option>
                <option value="tata_kelola">Tata Kelola Pemerintahan</option>
                <option value="lainnya">Inovasi Daerah Lainnya</option>
              </select>
            </div>
          </div>

          {/* Grid 2: Tanggal Uji Coba & Penerapan */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Tanggal Mulai Uji Coba</label>
              <input
                type="date"
                value={mulaiUjiCoba}
                onChange={(e) => setMulaiUjiCoba(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Tanggal Penerapan Awal *</label>
              <input
                type="date"
                value={mulaiPenerapan}
                onChange={(e) => setMulaiPenerapan(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
              <span className="text-[10px] text-slate-400">Harus dalam rentang 1 Jan 2025 - 31 Des 2026</span>
            </div>
          </div>

          {/* Rancang Bangun */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="font-bold text-slate-700">Rancang Bangun &amp; Pokok Inovasi *</label>
              <span className={`text-[11px] font-bold ${kataCount >= 300 ? 'text-emerald-600' : 'text-amber-600'}`}>
                {kataCount} / 300 Kata Min
              </span>
            </div>
            <textarea
              rows={5}
              placeholder="Jelaskan latar belakang, permasalahan yang dihadapi, solusi inovatif, serta mekanisme pelaksanaan..."
              value={rancangBangun}
              onChange={(e) => setRancangBangun(e.target.value)}
              className="w-full p-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500 leading-relaxed text-xs"
              required
            />
          </div>

          {/* Tujuan, Manfaat, Hasil */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Tujuan Inovasi *</label>
              <textarea
                rows={3}
                placeholder="Tujuan utama..."
                value={tujuan}
                onChange={(e) => setTujuan(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
                required
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Manfaat Utama</label>
              <textarea
                rows={3}
                placeholder="Manfaat bagi warga/pemda..."
                value={manfaat}
                onChange={(e) => setManfaat(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Hasil &amp; Capaian</label>
              <textarea
                rows={3}
                placeholder="Output kuantitatif..."
                value={hasil}
                onChange={(e) => setHasil(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
            </div>
          </div>

          {/* Anggaran & PIC */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2 border-t">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Besar Anggaran (Rp)</label>
              <input
                type="number"
                placeholder="150000000"
                value={anggaran}
                onChange={(e) => setAnggaran(e.target.value ? Number(e.target.value) : '')}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Sumber Anggaran</label>
              <input
                type="text"
                placeholder="APBD 2024"
                value={sumberAnggaran}
                onChange={(e) => setSumberAnggaran(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Nama Penanggung Jawab (PIC)</label>
              <input
                type="text"
                placeholder="Beto Nale"
                value={picNama}
                onChange={(e) => setPicNama(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">No Kontak (HP/WA)</label>
              <input
                type="text"
                placeholder="08123456789"
                value={picKontak}
                onChange={(e) => setPicKontak(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-xl"
              />
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex justify-end space-x-2 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center space-x-2 px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl shadow"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Memproses...' : 'Simpan Inovasi'}</span>
            </button>
          </div>

        </form>

      </div>
    </div>
  );
};
