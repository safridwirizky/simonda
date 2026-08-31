import React, { useState } from 'react';
import { InovasiDetail, NilaiBukti, UserProfile } from '../types';
import { BASIS_KEMANFAATAN, PARAMETER_KEMANFAATAN, KLASIFIKASI_KEMATANGAN } from '../api';
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Building2,
  Upload,
  Link as LinkIcon,
  ShieldCheck,
  Edit,
  Trash2,
  Check,
  XCircle,
  FileText,
  Send,
  Calendar,
  ExternalLink,
} from 'lucide-react';

interface InovasiDetailViewProps {
  inovasi: InovasiDetail;
  user: UserProfile | null;
  onBack: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onSubmit: () => void;
  onVerifyInovasi: (keputusan: 'terima' | 'revisi', catatan: string) => void;
  onUpdateNilai: (
    indikatorId: number,
    data: { pilihan: number; basis_ukur?: string; catatan?: string; tautan?: string }
  ) => Promise<void>;
  onUploadBerkas: (indikatorId: number, file: File) => Promise<void>;
  onDeleteBerkas: (indikatorId: number, berkasId: number) => Promise<void>;
  onVerifyNilai: (
    indikatorId: number,
    data: { keputusan: 'menunggu' | 'diterima' | 'ditolak'; catatan: string }
  ) => Promise<void>;
}

export const InovasiDetailView: React.FC<InovasiDetailViewProps> = ({
  inovasi,
  user,
  onBack,
  onEdit,
  onDelete,
  onSubmit,
  onVerifyInovasi,
  onUpdateNilai,
  onUploadBerkas,
  onDeleteBerkas,
  onVerifyNilai,
}) => {
  const [activeTab, setActiveTab] = useState<'detail' | 'indikator'>('indikator');
  const [verifCatatan, setVerifCatatan] = useState('');
  const [selectedIndikator, setSelectedIndikator] = useState<NilaiBukti | null>(null);

  // States for updating an indicator item modal/drawer
  const [editPilihan, setEditPilihan] = useState<number>(0);
  const [editBasisUkur, setEditBasisUkur] = useState<string>('');
  const [editCatatan, setEditCatatan] = useState<string>('');
  const [editTautan, setEditTautan] = useState<string>('');
  const [uploadingFiles, setUploadingFiles] = useState<File[]>([]);
  const [verifDecision, setVerifDecision] = useState<'diterima' | 'ditolak'>('diterima');
  const [verifIndikatorCatatan, setVerifIndikatorCatatan] = useState<string>('');

  const [saving, setSaving] = useState(false);
  const [deletingBerkasId, setDeletingBerkasId] = useState<number | null>(null);

  const openIndikatorModal = (b: NilaiBukti) => {
    setSelectedIndikator(b);
    setEditPilihan(b.pilihan);
    setEditBasisUkur(b.basis_ukur || '');
    setEditCatatan(b.catatan || '');
    setEditTautan(b.tautan || '');
    setUploadingFiles([]);
    setVerifDecision(b.verifikasi === 'ditolak' ? 'ditolak' : 'diterima');
    setVerifIndikatorCatatan(b.catatan_verifikator || '');
  };

  const handleSaveIndikatorChoice = async () => {
    if (!selectedIndikator) return;
    setSaving(true);
    try {
      await onUpdateNilai(selectedIndikator.indikator_id, {
        pilihan: editPilihan,
        basis_ukur: editBasisUkur,
        catatan: editCatatan,
        tautan: editTautan,
      });

      for (const file of uploadingFiles) {
        await onUploadBerkas(selectedIndikator.indikator_id, file);
      }

      setSelectedIndikator(null);
    } catch (e: any) {
      alert(e.message || 'Gagal menyimpan data indicator.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteBerkas = async (berkasId: number) => {
    if (!selectedIndikator) return;
    if (!confirm('Hapus berkas ini? Berkas akan dihapus permanen dari penyimpanan.')) return;
    setDeletingBerkasId(berkasId);
    try {
      await onDeleteBerkas(selectedIndikator.indikator_id, berkasId);
      setSelectedIndikator({
        ...selectedIndikator,
        berkas: selectedIndikator.berkas.filter((b) => b.id !== berkasId),
      });
    } catch (e: any) {
      alert(e.message || 'Gagal menghapus berkas.');
    } finally {
      setDeletingBerkasId(null);
    }
  };

  const handleSaveVerifikasiNilai = async () => {
    if (!selectedIndikator) return;
    setSaving(true);
    try {
      await onVerifyNilai(selectedIndikator.indikator_id, {
        keputusan: verifDecision,
        catatan: verifIndikatorCatatan,
      });
      setSelectedIndikator(null);
    } catch (e: any) {
      alert(e.message || 'Gagal menyimpan keputusan verifikasi.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Top Navigation & Status Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <button
          onClick={onBack}
          className="inline-flex items-center space-x-2 text-sm font-semibold text-slate-600 hover:text-slate-900 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Kembali ke Daftar Inovasi</span>
        </button>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {inovasi.bisa_diubah && (
            <>
              <button
                onClick={onEdit}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold transition"
              >
                <Edit className="w-3.5 h-3.5" />
                <span>Edit Inovasi</span>
              </button>

              <button
                onClick={onDelete}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Hapus</span>
              </button>
            </>
          )}

          {inovasi.status !== 'diajukan' && inovasi.status !== 'terverifikasi' && (
            <button
              onClick={onSubmit}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow transition"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Ajukan Verifikasi</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Title Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-500">
            <Building2 className="w-4 h-4 text-slate-400" />
            <span>{inovasi.opd.nama}</span>
          </div>

          <div className="flex items-center space-x-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold capitalize ${
                inovasi.status === 'terverifikasi'
                  ? 'bg-emerald-100 text-emerald-800'
                  : inovasi.status === 'diajukan'
                  ? 'bg-blue-100 text-blue-800'
                  : inovasi.status === 'revisi'
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-slate-100 text-slate-800'
              }`}
            >
              Status: {inovasi.status}
            </span>

            {inovasi.layak ? (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Layak IGA Kemendagri
              </span>
            ) : (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
                Belum Memenuhi Syarat
              </span>
            )}

            <span
              className={`px-3 py-1 rounded-full text-xs font-bold border ${
                KLASIFIKASI_KEMATANGAN[inovasi.klasifikasi_kematangan].badge
              }`}
              title={KLASIFIKASI_KEMATANGAN[inovasi.klasifikasi_kematangan].deskripsi}
            >
              {KLASIFIKASI_KEMATANGAN[inovasi.klasifikasi_kematangan].label}
            </span>
          </div>
        </div>

        <h1 className="text-2xl font-extrabold text-slate-900 leading-snug">{inovasi.nama}</h1>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-3 border-t border-slate-100 text-xs">
          <div>
            <span className="text-slate-400 block font-medium">Urusan Utama</span>
            <span className="font-bold text-slate-800">{inovasi.urusan || '-'}</span>
          </div>
          <div>
            <span className="text-slate-400 block font-medium">Tahapan Inovasi</span>
            <span className="font-bold text-slate-800 capitalize">{inovasi.tahapan.replace('_', ' ')}</span>
          </div>
          <div>
            <span className="text-slate-400 block font-medium">Jenis Inovasi</span>
            <span className="font-bold text-slate-800 capitalize">{inovasi.jenis.replace('_', ' ')}</span>
          </div>
          <div>
            <span className="text-slate-400 block font-medium">Skor SID Terverifikasi</span>
            <span className="font-bold text-emerald-600 text-sm">
              {inovasi.skor_terverifikasi} / 111 ({inovasi.persen_terverifikasi}%)
            </span>
          </div>
        </div>

        {/* Verification Alert Banner */}
        {user?.bisa_verifikasi && inovasi.status === 'diajukan' && (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl space-y-3">
            <div className="flex items-center space-x-2 text-amber-900 font-bold text-xs">
              <ShieldCheck className="w-4 h-4 text-amber-600" />
              <span>Inovasi Menunggu Keputusan Verifikator Bapperida</span>
            </div>
            <textarea
              placeholder="Tulis catatan atau arahan perbaikan bila dikembalikan..."
              value={verifCatatan}
              onChange={(e) => setVerifCatatan(e.target.value)}
              className="w-full text-xs p-2.5 bg-white border border-amber-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              rows={2}
            />
            <div className="flex items-center space-x-2">
              <button
                onClick={() => onVerifyInovasi('terima', verifCatatan)}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-lg shadow"
              >
                Setujui Inovasi
              </button>
              <button
                onClick={() => onVerifyInovasi('revisi', verifCatatan)}
                className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs rounded-lg shadow"
              >
                Kembalikan Perlu Revisi
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Tabs Selector */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab('indikator')}
          className={`pb-3 px-4 font-bold text-sm border-b-2 transition ${
            activeTab === 'indikator'
              ? 'border-emerald-500 text-emerald-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Penilaian 20 Indikator SID ({inovasi.skor_terverifikasi} / 111 Poin)
        </button>

        <button
          onClick={() => setActiveTab('detail')}
          className={`pb-3 px-4 font-bold text-sm border-b-2 transition ${
            activeTab === 'detail'
              ? 'border-emerald-500 text-emerald-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Rancang Bangun &amp; Profil Inovasi
        </button>
      </div>

      {/* TAB 1: 20 Indikator SID Assessment */}
      {activeTab === 'indikator' && (
        <div className="space-y-4">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs text-slate-600 flex items-center justify-between">
            <div>
              <span className="font-bold text-slate-800">Petunjuk Pengisian:</span> Klik pada baris indikator untuk memilih opsi parameter (1-3), mengunggah berkas bukti dukung, atau melakukan verifikasi.
            </div>
            <span className="font-bold text-emerald-600">
              Total Klaim OPD: {inovasi.skor_klaim} Poin
            </span>
          </div>

          <div className="space-y-3">
            {inovasi.bukti.map((b) => {
              const isFilled = b.pilihan > 0;
              const hasBukti = b.berkas.length > 0 || !!b.tautan;
              return (
                <div
                  key={b.indikator_id}
                  onClick={() => openIndikatorModal(b)}
                  className="bg-white p-4 rounded-xl border border-slate-200 hover:border-emerald-500/50 hover:shadow-sm transition cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="px-2 py-0.5 bg-slate-900 text-white font-black text-xs rounded">
                        Indikator {b.kode}
                      </span>
                      <span className="text-xs font-bold text-slate-800">{b.nama_indikator}</span>
                      {b.wajib && (
                        <span className="text-[10px] bg-rose-100 text-rose-800 font-bold px-1.5 py-0.5 rounded">
                          Mandatori
                        </span>
                      )}
                    </div>

                    <div className="text-xs text-slate-500">
                      Variabel: <span className="font-semibold text-slate-700">{b.variabel}</span> &bull; Bobot: {b.bobot}
                    </div>

                    {isFilled ? (
                      <p className={`text-xs font-medium ${hasBukti ? 'text-emerald-700' : 'text-amber-600'}`}>
                        Parameter Terpilih ({b.pilihan}):{' '}
                        {b.pilihan === 1 ? b.parameter_1 : b.pilihan === 2 ? b.parameter_2 : b.parameter_3}
                        {!hasBukti && ' — skor belum terhitung, menunggu berkas atau tautan'}
                      </p>
                    ) : (
                      <p className="text-xs text-rose-500 font-medium italic">Belum diisi oleh OPD</p>
                    )}
                  </div>

                  <div className="flex items-center space-x-4 self-end sm:self-center shrink-0">
                    <div className="text-right">
                      <div className="text-xs text-slate-400 font-medium">Skor Baris</div>
                      <div className="text-sm font-extrabold text-slate-900">
                        {b.skor} <span className="text-xs text-slate-400 font-normal">/ {b.skor_maks}</span>
                      </div>
                    </div>

                    <div>
                      {b.verifikasi === 'diterima' ? (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                          <Check className="w-3.5 h-3.5" />
                          <span>Diterima</span>
                        </span>
                      ) : b.verifikasi === 'ditolak' ? (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800">
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Ditolak</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800">
                          <Clock className="w-3.5 h-3.5" />
                          <span>Menunggu</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 2: Inovasi Detail & Rancang Bangun */}
      {activeTab === 'detail' && (
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6 text-xs sm:text-sm">
          
          <div>
            <h3 className="text-sm font-bold text-slate-900 border-b pb-2 mb-3">Rancang Bangun &amp; Pokok Inovasi</h3>
            <div className="p-4 bg-slate-50 rounded-xl text-slate-800 leading-relaxed whitespace-pre-line">
              {inovasi.rancang_bangun || 'Belum diisi.'}
            </div>
            <div className="mt-1 text-right text-xs text-slate-400">
              Jumlah kata: {inovasi.rancang_bangun ? inovasi.rancang_bangun.trim().split(/\s+/).length : 0} kata (minimal 300 kata).
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="font-bold text-slate-900 mb-1 text-xs">Tujuan Inovasi</h4>
              <p className="text-slate-700 text-xs">{inovasi.tujuan || '-'}</p>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="font-bold text-slate-900 mb-1 text-xs">Manfaat Utama</h4>
              <p className="text-slate-700 text-xs">{inovasi.manfaat || '-'}</p>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl">
              <h4 className="font-bold text-slate-900 mb-1 text-xs">Capaian &amp; Hasil</h4>
              <p className="text-slate-700 text-xs">{inovasi.hasil || '-'}</p>
            </div>
          </div>

          <div className="border-t pt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-slate-400 block font-medium">Pelaksana Inovasi</span>
              <span className="font-bold text-slate-800">{inovasi.nama_inisiator || inovasi.inisiator}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Bentuk Inovasi</span>
              <span className="font-bold text-slate-800 capitalize">{inovasi.bentuk.replace('_', ' ')}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Waktu Penerapan Awal</span>
              <span className="font-bold text-slate-800">{inovasi.mulai_penerapan || '-'}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Anggaran &amp; Sumber</span>
              <span className="font-bold text-slate-800">
                {inovasi.anggaran ? `Rp ${inovasi.anggaran.toLocaleString('id-ID')}` : '-'} ({inovasi.sumber_anggaran || '-'})
              </span>
            </div>
          </div>

        </div>
      )}

      {/* Modal / Drawer for Indikator Parameter & Evidence Selection */}
      {selectedIndikator && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl border border-slate-200 space-y-5">
            
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <span className="px-2 py-0.5 bg-slate-900 text-white font-bold text-xs rounded mr-2">
                  Indikator {selectedIndikator.kode}
                </span>
                <h3 className="text-base font-bold text-slate-900 inline">
                  {selectedIndikator.nama_indikator}
                </h3>
              </div>
              <button
                onClick={() => setSelectedIndikator(null)}
                className="text-slate-400 hover:text-slate-600 font-bold text-lg"
              >
                &times;
              </button>
            </div>

            {/* Basis Ukur (khusus indikator 33: Kemanfaatan Inovasi, 6 basis a-f) */}
            {selectedIndikator.nomor === 33 && (
              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-700">
                  Basis Ukur Kemanfaatan (wajib pilih salah satu):
                </label>
                <select
                  value={editBasisUkur}
                  onChange={(e) => setEditBasisUkur(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="">-- Pilih basis ukur --</option>
                  {BASIS_KEMANFAATAN.map((b) => (
                    <option key={b.kode} value={b.kode}>
                      {b.kode.toUpperCase()} - {b.label}
                    </option>
                  ))}
                </select>
                {!editBasisUkur && editPilihan > 0 && (
                  <p className="text-[11px] text-amber-600 font-semibold">
                    Pilih basis ukur dulu — ambang parameter di bawah berbeda untuk tiap basis.
                  </p>
                )}
              </div>
            )}

            {/* Parameter Selection Cards */}
            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-700">Pilih Parameter Penilaian (0 - 3):</label>

              {(() => {
                const [p1, p2, p3] =
                  selectedIndikator.nomor === 33
                    ? PARAMETER_KEMANFAATAN[editBasisUkur || 'a']
                    : [selectedIndikator.parameter_1, selectedIndikator.parameter_2, selectedIndikator.parameter_3];
                return [
                  { val: 0, label: '0 - Belum Memenuhi / Kosong' },
                  { val: 1, label: `1 - ${p1}` },
                  { val: 2, label: `2 - ${p2}` },
                  { val: 3, label: `3 - ${p3}` },
                ];
              })().map((opt) => (
                <div
                  key={opt.val}
                  onClick={() => setEditPilihan(opt.val)}
                  className={`p-3 rounded-xl border text-xs cursor-pointer transition ${
                    editPilihan === opt.val
                      ? 'border-emerald-500 bg-emerald-50/70 font-bold text-emerald-950 ring-2 ring-emerald-500/20'
                      : 'border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700'
                  }`}
                >
                  {opt.label}
                </div>
              ))}
            </div>

            {/* Catatan & Tautan Bukti Dukung */}
            <div className="space-y-3 pt-2">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Catatan / Keterangan Bukti Dukung
                </label>
                <input
                  type="text"
                  placeholder="Tulis uraian singkat bukti dukung..."
                  value={editCatatan}
                  onChange={(e) => setEditCatatan(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Tautan / Link Google Drive / Website
                </label>
                <p className="text-[11px] text-slate-500 mb-1">
                  Berkas di atas 10MB tidak bisa diunggah langsung — isi tautan Google Drive
                  atau sejenisnya di sini sebagai gantinya, skor tetap terhitung.
                </p>
                <input
                  type="url"
                  placeholder="https://..."
                  value={editTautan}
                  onChange={(e) => setEditTautan(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Berkas Bukti Dukung Terunggah
                </label>
                {editPilihan > 0 && selectedIndikator.berkas.length === 0 && uploadingFiles.length === 0 && !editTautan && (
                  <p className="text-[11px] text-amber-600 font-semibold mb-1">
                    Skor baris ini tetap 0 sampai ada berkas atau tautan — parameter saja tidak cukup.
                  </p>
                )}
                {selectedIndikator.berkas.length > 0 ? (
                  <ul className="space-y-1 mb-2">
                    {selectedIndikator.berkas.map((b) => (
                      <li
                        key={b.id}
                        className="flex items-center justify-between gap-2 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5"
                      >
                        <a
                          href={b.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1 text-xs text-emerald-600 font-semibold hover:underline min-w-0"
                        >
                          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{b.nama_asli}</span>
                        </a>
                        <button
                          type="button"
                          disabled={deletingBerkasId === b.id}
                          onClick={() => handleDeleteBerkas(b.id)}
                          className="text-rose-500 hover:text-rose-700 shrink-0 disabled:opacity-50"
                          title="Hapus berkas ini"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-400 italic mb-2">Belum ada berkas diunggah.</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Tambah Berkas Baru (boleh lebih dari satu, maks 10MB per berkas)
                </label>
                <input
                  type="file"
                  multiple
                  onChange={(e) => setUploadingFiles(Array.from(e.target.files || []))}
                  className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                />
                {uploadingFiles.length > 0 && (
                  <p className="text-[11px] text-slate-500 mt-1">
                    {uploadingFiles.length} berkas dipilih, akan diunggah saat disimpan.
                  </p>
                )}
              </div>
            </div>

            {/* Operator Save Button */}
            <div className="flex justify-end space-x-2 pt-3 border-t">
              <button
                onClick={() => setSelectedIndikator(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900"
              >
                Batal
              </button>
              <button
                disabled={saving}
                onClick={handleSaveIndikatorChoice}
                className="px-5 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl shadow"
              >
                {saving ? 'Menyimpan...' : 'Simpan Parameter OPD'}
              </button>
            </div>

            {/* Verifier Section if user is Verifier */}
            {user?.bisa_verifikasi && (
              <div className="p-4 bg-slate-900 text-white rounded-xl space-y-3 mt-4">
                <div className="text-xs font-bold text-amber-400 flex items-center space-x-1.5">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Panel Verifikasi Parameter oleh Bapperida</span>
                </div>

                <div className="flex items-center space-x-4 text-xs">
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="verifDec"
                      checked={verifDecision === 'diterima'}
                      onChange={() => setVerifDecision('diterima')}
                    />
                    <span>Setujui (Diterima)</span>
                  </label>
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="verifDec"
                      checked={verifDecision === 'ditolak'}
                      onChange={() => setVerifDecision('ditolak')}
                    />
                    <span>Tolak (Minta Perbaikan)</span>
                  </label>
                </div>

                <input
                  type="text"
                  placeholder="Catatan verifikator untuk OPD..."
                  value={verifIndikatorCatatan}
                  onChange={(e) => setVerifIndikatorCatatan(e.target.value)}
                  className="w-full text-xs p-2 bg-slate-800 text-white border border-slate-700 rounded-lg focus:outline-none"
                />

                <button
                  disabled={saving}
                  onClick={handleSaveVerifikasiNilai}
                  className="w-full py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs rounded-lg shadow"
                >
                  Simpan Keputusan Verifikasi
                </button>
              </div>
            )}

          </div>
        </div>
      )}

    </div>
  );
};
