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

export const URUSAN = [
  'Pendidikan',
  'Kesehatan',
  'Pekerjaan Umum dan Penataan Ruang',
  'Perumahan Rakyat dan Kawasan Permukiman',
  'Ketenteraman, Ketertiban Umum, dan Perlindungan Masyarakat',
  'Sosial',
  'Tenaga Kerja',
  'Pemberdayaan Perempuan dan Perlindungan Anak',
  'Pangan',
  'Pertanahan',
  'Lingkungan Hidup',
  'Administrasi Kependudukan dan Pencatatan Sipil',
  'Pemberdayaan Masyarakat dan Desa',
  'Pengendalian Penduduk dan Keluarga Berencana',
  'Perhubungan',
  'Komunikasi dan Informatika',
  'Koperasi, Usaha Kecil, dan Menengah',
  'Penanaman Modal',
  'Kepemudaan dan Olah Raga',
  'Kebudayaan',
  'Perpustakaan',
  'Kearsipan',
  'Kelautan dan Perikanan',
  'Pariwisata',
  'Pertanian',
  'Kehutanan',
  'Energi dan Sumber Daya Mineral',
  'Perdagangan',
  'Perindustrian',
  'Transmigrasi',
  'Fungsi Penunjang / Sekretariat / Perencanaan',
];

// Kosong berarti origin yang sama (proxy Vite dev, atau Nginx di produksi).
const API_BASE = import.meta.env.VITE_API_URL || '';

const getHeaders = () => {
  const token = localStorage.getItem('simonda_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const getAuthHeader = (): Record<string, string> => {
  const token = localStorage.getItem('simonda_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// Django Ninja membalas galat sebagai {"detail": "pesan"} atau, untuk galat
// validasi, {"detail": [{"msg": "...", ...}, ...]}.
async function extractError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
    }
    return data.message || fallback;
  } catch {
    return fallback;
  }
}

export async function fetchProfile(): Promise<UserProfile | null> {
  const token = localStorage.getItem('simonda_token');
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/auth/saya`, { headers: getHeaders() });
    if (!res.ok) {
      localStorage.removeItem('simonda_token');
      return null;
    }
    return await res.json();
  } catch {
    return null;
  }
}

export async function login(username: string, password: string): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/api/auth/masuk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new Error(await extractError(res, 'Login gagal'));
  }
  const data = await res.json();
  localStorage.setItem('simonda_token', data.akses);

  const profile = await fetchProfile();
  if (!profile) {
    localStorage.removeItem('simonda_token');
    throw new Error('Gagal memuat profil setelah masuk.');
  }
  return profile;
}

export async function logout(): Promise<void> {
  localStorage.removeItem('simonda_token');
}

export async function fetchRingkasan(): Promise<RingkasanStatistik> {
  const res = await fetch(`${API_BASE}/api/statistik/ringkasan`, { headers: getHeaders() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengambil statistik ringkasan'));
  return await res.json();
}

export async function fetchInovasiList(params?: any): Promise<InovasiRingkas[]> {
  let url = `${API_BASE}/api/inovasi`;
  if (params) {
    const qp = new URLSearchParams(params).toString();
    if (qp) url += `?${qp}`;
  }
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengambil daftar inovasi'));
  return await res.json();
}

export async function fetchInovasiDetail(id: number): Promise<InovasiDetail> {
  const res = await fetch(`${API_BASE}/api/inovasi/${id}`, { headers: getHeaders() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengambil rincian inovasi'));
  return await res.json();
}

export async function createInovasi(data: any): Promise<InovasiDetail> {
  const res = await fetch(`${API_BASE}/api/inovasi`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal membuat inovasi'));
  return await res.json();
}

export async function updateInovasi(id: number, data: any): Promise<InovasiDetail> {
  const res = await fetch(`${API_BASE}/api/inovasi/${id}`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal memperbarui inovasi'));
  return await res.json();
}

export async function deleteInovasi(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/inovasi/${id}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal menghapus inovasi'));
}

export async function submitInovasi(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/inovasi/${id}/ajukan`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengajukan inovasi'));
}

export async function verifyInovasi(id: number, keputusan: 'terima' | 'revisi', catatan: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/inovasi/${id}/verifikasi`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ keputusan, catatan }),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal memverifikasi inovasi'));
}

export async function updateNilaiBukti(
  inovasiId: number,
  indikatorId: number,
  data: { pilihan: number; basis_ukur?: string; catatan?: string; tautan?: string }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/inovasi/${inovasiId}/nilai/${indikatorId}`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal memperbarui nilai indikator'));
}

export async function uploadBerkasBukti(inovasiId: number, indikatorId: number, file: File): Promise<void> {
  const formData = new FormData();
  formData.append('berkas', file);

  const res = await fetch(`${API_BASE}/api/inovasi/${inovasiId}/nilai/${indikatorId}/berkas`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: formData,
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengunggah berkas bukti'));
}

export async function deleteBerkasBukti(inovasiId: number, indikatorId: number, berkasId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/inovasi/${inovasiId}/nilai/${indikatorId}/berkas/${berkasId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal menghapus berkas bukti'));
}

export async function verifyNilaiBukti(
  inovasiId: number,
  indikatorId: number,
  data: { keputusan: 'menunggu' | 'diterima' | 'ditolak'; catatan: string }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/inovasi/${inovasiId}/nilai/${indikatorId}/verifikasi`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal memverifikasi nilai indikator'));
}

export async function fetchSpdData(): Promise<NilaiSPD[]> {
  const res = await fetch(`${API_BASE}/api/spd`, { headers: getHeaders() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengambil data SPD'));
  return await res.json();
}

export async function updateSpd(
  indikatorId: number,
  data: { pilihan: number; keterangan?: string; tautan?: string }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/spd/${indikatorId}`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal memperbarui SPD'));
}

export async function uploadBerkasSpd(indikatorId: number, file: File): Promise<void> {
  const formData = new FormData();
  formData.append('berkas', file);

  const res = await fetch(`${API_BASE}/api/spd/${indikatorId}/berkas`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: formData,
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengunggah berkas SPD'));
}

export async function deleteBerkasSpd(indikatorId: number, berkasId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/spd/${indikatorId}/berkas/${berkasId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal menghapus berkas SPD'));
}

export async function fetchRekapOpd(): Promise<RekapOPD[]> {
  const res = await fetch(`${API_BASE}/api/statistik/opd`, { headers: getHeaders() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengambil rekapitulasi OPD'));
  return await res.json();
}

export async function fetchOpdList(): Promise<OPD[]> {
  const res = await fetch(`${API_BASE}/api/opd`, { headers: getHeaders() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengambil daftar OPD'));
  return await res.json();
}

export async function fetchAkunOpdList(): Promise<AkunOPD[]> {
  const res = await fetch(`${API_BASE}/api/akun-opd`, { headers: getHeaders() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengambil daftar akun OPD'));
  return await res.json();
}

export async function createAkunOpd(data: {
  username: string;
  password: string;
  nama_depan?: string;
  opd_id: number;
  nip?: string;
  telepon?: string;
}): Promise<AkunOPD> {
  const res = await fetch(`${API_BASE}/api/akun-opd`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal membuat akun OPD'));
  return await res.json();
}

export async function nonaktifkanAkun(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/akun-opd/${id}/nonaktifkan`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal menonaktifkan akun'));
}

export async function aktifkanAkun(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/akun-opd/${id}/aktifkan`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengaktifkan akun'));
}

export async function resetSandiAkun(id: number, password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/akun-opd/${id}/reset-sandi`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mereset sandi akun'));
}

// Ekspor resmi format IGA (hanya inovasi terverifikasi dan layak). Endpoint ini
// terproteksi Bearer token sehingga tidak bisa dipakai lewat tautan <a href> biasa.
export async function exportIgaCsv(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/ekspor/iga`, { headers: getAuthHeader() });
  if (!res.ok) throw new Error(await extractError(res, 'Gagal mengekspor data ke CSV'));

  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : 'inovasi-rote-ndao.csv';

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
