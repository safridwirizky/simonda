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

// Indikator SID 33 "Kemanfaatan Inovasi" (Lampiran II butir 33) punya 6 basis
// ukur alternatif -- OPD memilih tepat satu, tiap basis punya ambang
// parameter 1-3 sendiri (lihat PARAMETER_KEMANFAATAN di bawah).
export const BASIS_KEMANFAATAN: { kode: string; label: string }[] = [
  { kode: 'a', label: 'Jumlah penerima manfaat (orang)' },
  { kode: 'b', label: 'Cakupan unit penerima manfaat (persentase dari unit sasaran)' },
  { kode: 'c', label: 'Efisiensi belanja sebelum dan sesudah inovasi' },
  { kode: 'd', label: 'Penambahan pendapatan sebelum dan sesudah inovasi' },
  { kode: 'e', label: 'Jumlah produk yang dihasilkan atau diperjualbelikan' },
  { kode: 'f', label: 'Tren kinerja positif dalam periode pengukuran' },
];

export const PARAMETER_KEMANFAATAN: Record<string, [string, string, string]> = {
  a: [
    'Cakupan penerima manfaat 1-200 orang',
    'Cakupan penerima manfaat 201-500 orang',
    'Cakupan penerima manfaat 501 orang atau lebih',
  ],
  b: [
    'Cakupan unit penerima manfaat 5,00% s.d. 20,00% dari unit sasaran',
    'Cakupan unit penerima manfaat 20,01% s.d. 50,00% dari unit sasaran',
    'Cakupan unit penerima manfaat di atas 50,00% dari unit sasaran',
  ],
  c: [
    'Efisiensi belanja sebesar 0,01% - 10,00%',
    'Efisiensi belanja sebesar 10,01% - 20,00%',
    'Efisiensi belanja sebesar 20,01% - 30,00%',
  ],
  d: [
    'Penambahan pendapatan sebesar 0,01% - 9,99%',
    'Penambahan pendapatan sebesar 10,00% - 19,99%',
    'Penambahan pendapatan sebesar ≥20%',
  ],
  e: [
    'Jumlah produk dihasilkan/diperjualbelikan 1-100 barang',
    'Jumlah produk dihasilkan/diperjualbelikan 101-200 barang',
    'Jumlah produk dihasilkan/diperjualbelikan lebih dari 200 barang',
  ],
  f: [
    'Tren kinerja positif dalam 1 periode waktu pengukuran',
    'Tren kinerja positif dalam 2 periode waktu pengukuran',
    'Tren kinerja positif dalam 3 periode waktu pengukuran',
  ],
};

// Klasifikasi kematangan per inovasi berdasarkan skor_klaim (0-111) -- bukan
// bagian pedoman resmi BSKDN, konvensi internal untuk memantau kesiapan tiap
// inovasi. Ambang batasnya harus sama persis dengan iga.KLASIFIKASI_KEMATANGAN
// di backend.
// Indikator SID yang bukti dukungnya lazim berupa surat/dokumen resmi (SK,
// surat penugasan, undangan bimtek, dsb) -- untuk baris ini modal menampilkan
// kolom nomor dan tanggal surat/dokumen tambahan. Harus sama persis dengan
// iga.INDIKATOR_PERLU_DOKUMEN di backend.
export const INDIKATOR_PERLU_DOKUMEN = [16, 17, 18, 20, 21, 22, 23, 24, 28, 31];

// Ekstensi berkas yang diterima per indikator SID. Default PDF saja, kecuali
// indikator 35 (Video inovasi daerah, wajib video) dan indikator 25 & 30
// (Sosialisasi Inovasi Daerah, Layanan Terintegrasi -- PDF atau gambar).
// Harus sama persis dengan iga.ekstensi_sid_diizinkan() di backend --
// pengecekan yang sesungguhnya tetap dilakukan di server, ini cuma untuk
// atribut `accept` dan pesan bantuan di formulir.
export const EKSTENSI_SPD = ['pdf'];
export const EKSTENSI_SID_DEFAULT = ['pdf'];
export const EKSTENSI_SID_GAMBAR = ['pdf', 'jpg', 'jpeg', 'png'];
export const EKSTENSI_SID_VIDEO = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'wmv', 'm4v', '3gp', 'mpeg', 'mpg'];
const INDIKATOR_SID_VIDEO = [35];
const INDIKATOR_SID_GAMBAR = [25, 30];

export function ekstensiSidDiizinkan(nomorIndikator: number): string[] {
  if (INDIKATOR_SID_VIDEO.includes(nomorIndikator)) return EKSTENSI_SID_VIDEO;
  if (INDIKATOR_SID_GAMBAR.includes(nomorIndikator)) return EKSTENSI_SID_GAMBAR;
  return EKSTENSI_SID_DEFAULT;
}

export function acceptBerkas(ekstensi: string[]): string {
  return ekstensi.map((e) => `.${e}`).join(',');
}

export const KLASIFIKASI_KEMATANGAN: Record<
  'danger' | 'warning' | 'hijau',
  { label: string; deskripsi: string; badge: string; dot: string; solid: string }
> = {
  danger: {
    label: 'Skor Rendah',
    deskripsi: 'Skor 0 - 65',
    badge: 'bg-rose-100 text-rose-800 border-rose-200',
    dot: 'bg-rose-500',
    solid: 'bg-rose-500 text-white',
  },
  warning: {
    label: 'Skor Sedang',
    deskripsi: 'Skor 66 - 84',
    badge: 'bg-amber-100 text-amber-800 border-amber-200',
    dot: 'bg-amber-500',
    solid: 'bg-amber-500 text-white',
  },
  hijau: {
    label: 'Skor Tinggi',
    deskripsi: 'Skor 85 - 111',
    badge: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    dot: 'bg-emerald-500',
    solid: 'bg-emerald-500 text-white',
  },
};

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
  data: {
    pilihan: number;
    basis_ukur?: string;
    catatan?: string;
    tautan?: string;
    nomor_dokumen?: string;
    tanggal_dokumen?: string | null;
  }
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
