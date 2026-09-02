import React, { useState } from 'react';
import { NilaiSPD } from '../types';
import { FileSpreadsheet, Check, ExternalLink, Trash2 } from 'lucide-react';

interface SPDViewProps {
  spdData: NilaiSPD[] | null;
  onUpdateSpd: (
    indikatorId: number,
    data: { pilihan: number; keterangan?: string; tautan?: string }
  ) => Promise<void>;
  onUploadBerkas: (indikatorId: number, file: File) => Promise<void>;
  onDeleteBerkas: (indikatorId: number, berkasId: number) => Promise<void>;
}

export const SPDView: React.FC<SPDViewProps> = ({ spdData, onUpdateSpd, onUploadBerkas, onDeleteBerkas }) => {
  const [selectedSpd, setSelectedSpd] = useState<NilaiSPD | null>(null);
  const [editPilihan, setEditPilihan] = useState<number>(0);
  const [editKeterangan, setEditKeterangan] = useState<string>('');
  const [editTautan, setEditTautan] = useState<string>('');
  const [uploadingFiles, setUploadingFiles] = useState<File[]>([]);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  if (!spdData) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  const totalSkor = spdData.reduce((sum, item) => sum + item.skor, 0);
  const totalSkorMaks = spdData.reduce((sum, item) => sum + item.skor_maks, 0);

  const openModal = (item: NilaiSPD) => {
    setSelectedSpd(item);
    setEditPilihan(item.pilihan);
    setEditKeterangan(item.keterangan || '');
    setEditTautan(item.tautan || '');
    setUploadingFiles([]);
  };

  const handleSaveSpd = async () => {
    if (!selectedSpd) return;
    setSaving(true);
    try {
      await onUpdateSpd(selectedSpd.indikator_id, {
        pilihan: editPilihan,
        keterangan: editKeterangan,
        tautan: editTautan,
      });
      for (const file of uploadingFiles) {
        await onUploadBerkas(selectedSpd.indikator_id, file);
      }
      setSelectedSpd(null);
    } catch (e: any) {
      alert(e.message || 'Gagal menyimpan indikator SPD.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteBerkas = async (berkasId: number) => {
    if (!selectedSpd) return;
    if (!confirm('Hapus berkas ini? Berkas akan dihapus permanen dari penyimpanan.')) return;
    setDeletingId(berkasId);
    try {
      await onDeleteBerkas(selectedSpd.indikator_id, berkasId);
      setSelectedSpd({
        ...selectedSpd,
        berkas: selectedSpd.berkas.filter((b) => b.id !== berkasId),
      });
    } catch (e: any) {
      alert(e.message || 'Gagal menghapus berkas.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">

      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold text-emerald-600 mb-1 uppercase tracking-wider">
            <FileSpreadsheet className="w-4 h-4" />
            <span>Satuan Pemerintah Daerah (SPD)</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">15 Indikator SPD Kabupaten</h1>
          <p className="text-xs text-slate-500 mt-1 max-w-xl">
            20 baris skor institusi, SDM, dan ekosistem inovasi tingkat daerah. Diisi langsung oleh
            Bapperida, satu nilai per periode &mdash; tidak melalui alur klaim/verifikasi terpisah.
          </p>
        </div>

        <div className="bg-slate-900 text-white rounded-xl p-4 text-center shrink-0">
          <div className="text-[11px] text-slate-400 font-semibold uppercase">Total Skor SPD</div>
          <div className="text-3xl font-black text-emerald-400">
            {totalSkor.toFixed(2)} <span className="text-sm text-slate-400 font-normal">/ {totalSkorMaks.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Indikator List */}
      <div className="space-y-3">
        {spdData.map((item) => {
          const isFilled = item.pilihan > 0;
          const hasBukti = item.berkas.length > 0 || !!item.tautan;
          return (
            <div
              key={item.indikator_id}
              onClick={() => openModal(item)}
              className="bg-white p-5 rounded-2xl border border-slate-200 hover:border-emerald-500/50 hover:shadow-sm transition cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-1.5">
                <div className="flex items-center space-x-2">
                  <span className="px-2.5 py-0.5 bg-slate-900 text-white font-black text-xs rounded">
                    SPD {item.kode}
                  </span>
                  <span className="text-sm font-bold text-slate-900">{item.nama}</span>
                  {item.wajib && (
                    <span className="text-[10px] bg-rose-100 text-rose-800 font-bold px-2 py-0.5 rounded">
                      Mandatori
                    </span>
                  )}
                </div>

                <div className="text-xs text-slate-500">
                  Variabel: <span className="font-semibold text-slate-700">{item.variabel}</span> &bull; Bobot: {item.bobot}
                </div>

                {isFilled ? (
                  <p className={`text-xs font-medium ${hasBukti ? 'text-emerald-700' : 'text-amber-600'}`}>
                    Parameter Terpilih ({item.pilihan}):{' '}
                    {item.pilihan === 1 ? item.parameter_1 : item.pilihan === 2 ? item.parameter_2 : item.parameter_3}
                    {!hasBukti && ' — skor belum terhitung, menunggu berkas atau tautan'}
                  </p>
                ) : (
                  <p className="text-xs text-rose-500 font-medium italic">Belum diisi parameter</p>
                )}
              </div>

              <div className="flex items-center space-x-4 shrink-0 self-end sm:self-center">
                <div className="text-right">
                  <div className="text-[11px] text-slate-400 font-medium">Skor Baris</div>
                  <div className="text-sm font-extrabold text-slate-900">
                    {item.skor} <span className="text-xs text-slate-400 font-normal">/ {item.skor_maks}</span>
                  </div>
                </div>

                {isFilled && (
                  hasBukti ? (
                    <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                      <Check className="w-3.5 h-3.5" />
                      <span>
                        {item.berkas.length > 1
                          ? `Terisi (${item.berkas.length} berkas)`
                          : item.berkas.length === 1
                          ? 'Terisi'
                          : 'Terisi (tautan)'}
                      </span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800">
                      <span>Menunggu Bukti</span>
                    </span>
                  )
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal for SPD Indicator Selection */}
      {selectedSpd && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl border border-slate-200 space-y-4">

            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <span className="px-2 py-0.5 bg-slate-900 text-white font-bold text-xs rounded mr-2">
                  SPD {selectedSpd.kode}
                </span>
                <h3 className="text-base font-bold text-slate-900 inline">
                  {selectedSpd.nama}
                </h3>
              </div>
              <button onClick={() => setSelectedSpd(null)} className="text-slate-400 font-bold text-lg">
                &times;
              </button>
            </div>

            {/* Parameter selection options */}
            <div className="space-y-2 text-xs">
              <label className="block font-bold text-slate-700">Pilih Parameter Evaluasi:</label>
              {[
                { val: 0, label: '0 - Belum Memenuhi / Kosong' },
                { val: 1, label: `1 - ${selectedSpd.parameter_1}` },
                { val: 2, label: `2 - ${selectedSpd.parameter_2}` },
                { val: 3, label: `3 - ${selectedSpd.parameter_3}` },
              ].map((opt) => (
                <div
                  key={opt.val}
                  onClick={() => setEditPilihan(opt.val)}
                  className={`p-3 rounded-xl border cursor-pointer transition ${
                    editPilihan === opt.val
                      ? 'border-emerald-500 bg-emerald-50 font-bold text-emerald-950'
                      : 'border-slate-200 bg-slate-50 text-slate-700'
                  }`}
                >
                  {opt.label}
                </div>
              ))}
            </div>

            <div className="space-y-3 pt-2 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Link Tautan / Dokumen Pendukung
                </label>
                <p className="text-[11px] text-slate-500 mb-1">
                  Berkas di atas 1MB tidak bisa diunggah langsung — isi tautan Google Drive
                  atau sejenisnya di sini sebagai gantinya, skor tetap terhitung.
                </p>
                <input
                  type="url"
                  placeholder="https://..."
                  value={editTautan}
                  onChange={(e) => setEditTautan(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Keterangan</label>
                <input
                  type="text"
                  placeholder="Nomor SK / Perda / Laporan..."
                  value={editKeterangan}
                  onChange={(e) => setEditKeterangan(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Berkas Bukti Dukung Terunggah
                </label>
                {selectedSpd.berkas.length > 0 ? (
                  <ul className="space-y-1 mb-2">
                    {selectedSpd.berkas.map((b) => (
                      <li
                        key={b.id}
                        className="flex items-center justify-between gap-2 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5"
                      >
                        <a
                          href={b.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1 text-emerald-600 font-semibold hover:underline min-w-0"
                        >
                          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{b.nama_asli}</span>
                        </a>
                        <button
                          type="button"
                          disabled={deletingId === b.id}
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
                  <p className="text-slate-400 italic mb-2">Belum ada berkas diunggah.</p>
                )}
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Tambah Berkas Baru (boleh lebih dari satu, maks 1MB per berkas)
                </label>
                {editPilihan > 0 && selectedSpd.berkas.length === 0 && uploadingFiles.length === 0 && !editTautan && (
                  <p className="text-[11px] text-amber-600 font-semibold mb-1">
                    Skor baris ini tetap 0 sampai ada berkas atau tautan — parameter saja tidak cukup.
                  </p>
                )}
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

            <div className="flex justify-end space-x-2 pt-3 border-t">
              <button onClick={() => setSelectedSpd(null)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Batal
              </button>
              <button
                disabled={saving}
                onClick={handleSaveSpd}
                className="px-5 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl shadow"
              >
                {saving ? 'Menyimpan...' : 'Simpan SPD'}
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};
