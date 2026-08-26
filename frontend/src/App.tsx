import React, { useState, useEffect } from 'react';
import {
  UserProfile,
  RingkasanStatistik,
  InovasiRingkas,
  InovasiDetail,
  OPD,
  NilaiSPD,
  RekapOPD,
  AkunOPD,
} from './types';
import {
  fetchProfile,
  login,
  logout,
  fetchRingkasan,
  fetchInovasiList,
  fetchInovasiDetail,
  createInovasi,
  updateInovasi,
  deleteInovasi,
  submitInovasi,
  verifyInovasi,
  updateNilaiBukti,
  uploadBerkasBukti,
  deleteBerkasBukti,
  verifyNilaiBukti,
  fetchSpdData,
  updateSpd,
  uploadBerkasSpd,
  deleteBerkasSpd,
  fetchRekapOpd,
  fetchOpdList,
  exportIgaCsv,
  fetchAkunOpdList,
  createAkunOpd,
  nonaktifkanAkun,
  aktifkanAkun,
  resetSandiAkun,
} from './api';

import { Navbar } from './components/Navbar';
import { DashboardView } from './components/DashboardView';
import { InovasiListView } from './components/InovasiListView';
import { InovasiDetailView } from './components/InovasiDetailView';
import { SPDView } from './components/SPDView';
import { RekapOPDView } from './components/RekapOPDView';
import { KelolaAkunView } from './components/KelolaAkunView';
import { InovasiFormModal } from './components/InovasiFormModal';
import { LoginModal } from './components/LoginModal';

export default function App() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'inovasi' | 'spd' | 'rekap' | 'akun'>('dashboard');

  // Main state collections
  const [stats, setStats] = useState<RingkasanStatistik | null>(null);
  const [inovasiList, setInovasiList] = useState<InovasiRingkas[]>([]);
  const [opdList, setOpdList] = useState<OPD[]>([]);
  const [spdData, setSpdData] = useState<NilaiSPD[] | null>(null);
  const [rekapList, setRekapList] = useState<RekapOPD[]>([]);
  const [akunList, setAkunList] = useState<AkunOPD[]>([]);

  // Selected item detail state
  const [selectedInovasiId, setSelectedInovasiId] = useState<number | null>(null);
  const [selectedInovasiDetail, setSelectedInovasiDetail] = useState<InovasiDetail | null>(null);

  // Modals visibility
  const [showFormModal, setShowFormModal] = useState(false);
  const [editingInovasi, setEditingInovasi] = useState<InovasiDetail | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);

  const [loading, setLoading] = useState(true);

  // Load initial global application data
  const loadInitialData = async () => {
    setLoading(true);
    try {
      const uProfile = await fetchProfile();
      setUser(uProfile);

      if (!uProfile) {
        // Backend Django mewajibkan Bearer token di hampir semua endpoint.
        // Tanpa sesi masuk, tidak ada data yang bisa diambil.
        setStats(null);
        setInovasiList([]);
        setOpdList([]);
        setSpdData(null);
        setRekapList([]);
        setAkunList([]);
        return;
      }

      const [st, list, opds] = await Promise.all([
        fetchRingkasan(),
        fetchInovasiList(),
        fetchOpdList(),
      ]);

      setStats(st);
      setInovasiList(list);
      setOpdList(opds);

      if (uProfile.bisa_verifikasi) {
        const [spd, rkp, akun] = await Promise.all([fetchSpdData(), fetchRekapOpd(), fetchAkunOpdList()]);
        setSpdData(spd);
        setRekapList(rkp);
        setAkunList(akun);
      } else {
        setSpdData(null);
        setRekapList([]);
        setAkunList([]);
      }
    } catch (e) {
      console.error('Failed loading initial data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // Fetch Innovation Detail whenever an ID is selected
  useEffect(() => {
    if (selectedInovasiId) {
      fetchInovasiDetail(selectedInovasiId)
        .then((detail) => setSelectedInovasiDetail(detail))
        .catch((err) => {
          alert('Gagal memuat rincian inovasi: ' + err.message);
          setSelectedInovasiId(null);
        });
    } else {
      setSelectedInovasiDetail(null);
    }
  }, [selectedInovasiId]);

  // Auth Handlers
  const handleLogin = async (username: string, pass: string) => {
    await login(username, pass);
    await loadInitialData();
  };

  const handleLogout = async () => {
    await logout();
    setUser(null);
    await loadInitialData();
  };

  // Innovation Actions
  const handleSaveInovasiForm = async (formData: any) => {
    if (editingInovasi) {
      await updateInovasi(editingInovasi.id, formData);
      if (selectedInovasiId === editingInovasi.id) {
        const updated = await fetchInovasiDetail(editingInovasi.id);
        setSelectedInovasiDetail(updated);
      }
    } else {
      const newInv = await createInovasi(formData);
      setSelectedInovasiId(newInv.id);
      setActiveTab('inovasi');
    }
    await loadInitialData();
  };

  const handleDeleteInovasi = async () => {
    if (!selectedInovasiDetail) return;
    if (!confirm(`Apakah Anda yakin ingin menghapus inovasi "${selectedInovasiDetail.nama}"?`)) {
      return;
    }
    try {
      await deleteInovasi(selectedInovasiDetail.id);
      setSelectedInovasiId(null);
      setSelectedInovasiDetail(null);
      await loadInitialData();
    } catch (e: any) {
      alert(e.message || 'Gagal menghapus inovasi.');
    }
  };

  const handleSubmitInovasi = async () => {
    if (!selectedInovasiDetail) return;
    try {
      await submitInovasi(selectedInovasiDetail.id);
      const updated = await fetchInovasiDetail(selectedInovasiDetail.id);
      setSelectedInovasiDetail(updated);
      await loadInitialData();
      alert('Inovasi berhasil diajukan ke Bapperida!');
    } catch (e: any) {
      alert(e.message || 'Gagal mengajukan inovasi.');
    }
  };

  const handleVerifyInovasi = async (keputusan: 'terima' | 'revisi', catatan: string) => {
    if (!selectedInovasiDetail) return;
    try {
      await verifyInovasi(selectedInovasiDetail.id, keputusan, catatan);
      const updated = await fetchInovasiDetail(selectedInovasiDetail.id);
      setSelectedInovasiDetail(updated);
      await loadInitialData();
      alert(`Status inovasi berhasil diperbarui: ${keputusan.toUpperCase()}`);
    } catch (e: any) {
      alert(e.message || 'Gagal memverifikasi inovasi.');
    }
  };

  const handleUpdateNilai = async (
    indikatorId: number,
    data: { pilihan: number; basis_ukur?: string; catatan?: string; tautan?: string }
  ) => {
    if (!selectedInovasiDetail) return;
    await updateNilaiBukti(selectedInovasiDetail.id, indikatorId, data);
    const updated = await fetchInovasiDetail(selectedInovasiDetail.id);
    setSelectedInovasiDetail(updated);
    await loadInitialData();
  };

  const handleUploadBerkas = async (indikatorId: number, file: File) => {
    if (!selectedInovasiDetail) return;
    await uploadBerkasBukti(selectedInovasiDetail.id, indikatorId, file);
    const updated = await fetchInovasiDetail(selectedInovasiDetail.id);
    setSelectedInovasiDetail(updated);
  };

  const handleDeleteBerkas = async (indikatorId: number, berkasId: number) => {
    if (!selectedInovasiDetail) return;
    await deleteBerkasBukti(selectedInovasiDetail.id, indikatorId, berkasId);
    const updated = await fetchInovasiDetail(selectedInovasiDetail.id);
    setSelectedInovasiDetail(updated);
  };

  const handleVerifyNilai = async (
    indikatorId: number,
    data: { keputusan: 'menunggu' | 'diterima' | 'ditolak'; catatan: string }
  ) => {
    if (!selectedInovasiDetail) return;
    await verifyNilaiBukti(selectedInovasiDetail.id, indikatorId, data);
    const updated = await fetchInovasiDetail(selectedInovasiDetail.id);
    setSelectedInovasiDetail(updated);
    await loadInitialData();
  };

  // SPD Handlers. Django tidak punya alur klaim/verifikasi terpisah untuk SPD
  // (hanya verifikator yang boleh mengubahnya sama sekali), jadi cukup satu aksi simpan.
  const handleUpdateSpd = async (
    indikatorId: number,
    data: { pilihan: number; keterangan?: string; tautan?: string }
  ) => {
    await updateSpd(indikatorId, data);
    await loadInitialData();
  };

  const handleUploadBerkasSpd = async (indikatorId: number, file: File) => {
    await uploadBerkasSpd(indikatorId, file);
    await loadInitialData();
  };

  const handleDeleteBerkasSpd = async (indikatorId: number, berkasId: number) => {
    await deleteBerkasSpd(indikatorId, berkasId);
    await loadInitialData();
  };

  // Ekspor resmi format IGA lewat backend (hanya inovasi terverifikasi & layak).
  const handleExportCsv = async () => {
    try {
      await exportIgaCsv();
    } catch (e: any) {
      alert(e.message || 'Gagal mengekspor data ke CSV.');
    }
  };

  // Kelola Akun OPD (khusus verifikator/admin)
  const handleCreateAkun = async (data: {
    username: string;
    password: string;
    nama_depan?: string;
    opd_id: number;
    nip?: string;
    telepon?: string;
  }) => {
    await createAkunOpd(data);
    await loadInitialData();
  };

  const handleNonaktifkanAkun = async (id: number) => {
    await nonaktifkanAkun(id);
    await loadInitialData();
  };

  const handleAktifkanAkun = async (id: number) => {
    await aktifkanAkun(id);
    await loadInitialData();
  };

  const handleResetSandi = async (id: number, password: string) => {
    await resetSandiAkun(id, password);
    await loadInitialData();
  };

  if (loading && !stats) {
    return (
      <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center p-4">
        <div className="w-12 h-12 rounded-2xl bg-emerald-500 flex items-center justify-center text-slate-950 font-black text-2xl animate-bounce mb-3 shadow-lg shadow-emerald-500/30">
          S
        </div>
        <h2 className="text-lg font-bold">Memuat System SIMONDA...</h2>
        <p className="text-xs text-slate-400 mt-1">Indeks Inovasi Daerah Kemendagri &bull; Kab. Rote Ndao</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100/70 text-slate-900 flex flex-col font-sans">

      {/* Top Navbar */}
      <Navbar
        user={user}
        tahun={stats?.tahun ?? null}
        activeTab={activeTab}
        setActiveTab={(t) => {
          setSelectedInovasiId(null);
          setActiveTab(t);
        }}
        onOpenLogin={() => setShowLoginModal(true)}
        onLogout={handleLogout}
      />

      {/* Main Body View */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">

        {!user ? (
          <div className="max-w-md mx-auto text-center py-20 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500 flex items-center justify-center text-slate-950 font-black text-2xl mx-auto shadow-lg shadow-emerald-500/20">
              S
            </div>
            <h1 className="text-xl font-extrabold text-slate-900">Masuk untuk melihat data SIMONDA</h1>
            <p className="text-sm text-slate-500">
              Data inovasi daerah bersifat internal Pemkab Rote Ndao. Masuk dengan akun operator OPD
              atau verifikator Bapperida untuk melanjutkan.
            </p>
            <button
              onClick={() => setShowLoginModal(true)}
              className="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm shadow"
            >
              Masuk Akun
            </button>
          </div>
        ) : selectedInovasiDetail ? (
          <InovasiDetailView
            inovasi={selectedInovasiDetail}
            user={user}
            onBack={() => setSelectedInovasiId(null)}
            onEdit={() => {
              setEditingInovasi(selectedInovasiDetail);
              setShowFormModal(true);
            }}
            onDelete={handleDeleteInovasi}
            onSubmit={handleSubmitInovasi}
            onVerifyInovasi={handleVerifyInovasi}
            onUpdateNilai={handleUpdateNilai}
            onUploadBerkas={handleUploadBerkas}
            onDeleteBerkas={handleDeleteBerkas}
            onVerifyNilai={handleVerifyNilai}
          />
        ) : activeTab === 'dashboard' ? (
          <DashboardView
            stats={stats}
            user={user}
            onOpenNewInovasi={() => {
              setEditingInovasi(null);
              setShowFormModal(true);
            }}
            onNavigateTab={(tab) => setActiveTab(tab)}
            onExportCsv={handleExportCsv}
          />
        ) : activeTab === 'inovasi' ? (
          <InovasiListView
            inovasiList={inovasiList}
            opdList={opdList}
            user={user}
            onSelectInovasi={(id) => setSelectedInovasiId(id)}
            onOpenNewInovasi={() => {
              setEditingInovasi(null);
              setShowFormModal(true);
            }}
          />
        ) : activeTab === 'spd' ? (
          <SPDView
            spdData={spdData}
            onUpdateSpd={handleUpdateSpd}
            onUploadBerkas={handleUploadBerkasSpd}
            onDeleteBerkas={handleDeleteBerkasSpd}
          />
        ) : activeTab === 'rekap' ? (
          <RekapOPDView
            rekapList={rekapList}
            inovasiList={inovasiList}
            onSelectInovasi={(id) => {
              setSelectedInovasiId(id);
              setActiveTab('inovasi');
            }}
          />
        ) : activeTab === 'akun' ? (
          <KelolaAkunView
            akunList={akunList}
            opdList={opdList}
            onCreate={handleCreateAkun}
            onNonaktifkan={handleNonaktifkanAkun}
            onAktifkan={handleAktifkanAkun}
            onResetSandi={handleResetSandi}
          />
        ) : null}

      </main>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 text-xs py-6 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-white">SIMONDA Rote Ndao</span>
            <span>&bull; Sistem Monitoring Inovasi Daerah</span>
          </div>
          <div>&copy; {new Date().getFullYear()} Bapperida Kabupaten Rote Ndao &bull; IGA Kemendagri</div>
        </div>
      </footer>

      {/* Form Modal for Creating/Editing Innovation */}
      {showFormModal && (
        <InovasiFormModal
          initialData={editingInovasi}
          opdList={opdList}
          user={user}
          onClose={() => {
            setShowFormModal(false);
            setEditingInovasi(null);
          }}
          onSave={handleSaveInovasiForm}
        />
      )}

      {/* Login Modal */}
      {showLoginModal && (
        <LoginModal
          onClose={() => setShowLoginModal(false)}
          onLogin={handleLogin}
        />
      )}

    </div>
  );
}
