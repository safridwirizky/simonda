export interface OPD {
  id: number;
  kode: string;
  nama: string;
  singkatan?: string;
  aktif?: boolean;
}

export interface UserProfile {
  id: number;
  username: string;
  nama: string;
  peran: 'admin' | 'verifikator' | 'operator';
  bisa_verifikasi: boolean;
  opd?: OPD | null;
}

export interface AkunOPD {
  id: number;
  username: string;
  nama: string;
  opd: OPD;
  nip?: string;
  telepon?: string;
  is_active: boolean;
}

export interface Periode {
  id: number;
  tahun: number;
  window_buka?: string | null;
  window_tutup?: string | null;
  pembagi_minimal: number;
  min_urusan_yandas: number;
  aktif: boolean;
  catatan?: string;
}

export interface Indikator {
  id: number;
  periode_id: number;
  aspek: 'spd' | 'sid';
  nomor: number;
  sub: string;
  kode: string;
  variabel: string;
  nama: string;
  bobot: number;
  skor_maks: number;
  wajib: boolean;
  parameter_1: string;
  parameter_2: string;
  parameter_3: string;
  panduan?: string;
  aktif: boolean;
}

export interface BerkasFile {
  id: number;
  url: string;
  nama_asli: string;
  diunggah_pada: string;
}

export interface NilaiBukti {
  indikator_id: number;
  kode: string;
  nomor: number;
  variabel: string;
  nama_indikator: string;
  bobot: number;
  wajib: boolean;
  parameter_1: string;
  parameter_2: string;
  parameter_3: string;
  pilihan: number; // 0, 1, 2, 3
  basis_ukur?: string;
  skor: number;
  skor_maks: number;
  catatan?: string;
  tautan?: string;
  berkas: BerkasFile[];
  verifikasi: 'menunggu' | 'diterima' | 'ditolak';
  catatan_verifikator?: string;
  diperbarui_pada?: string | null;
}

export interface InovasiRingkas {
  id: number;
  nama: string;
  tahapan: 'inisiatif' | 'uji_coba' | 'penerapan';
  jenis: 'digital' | 'non_digital';
  bentuk: 'tata_kelola' | 'pelayanan_publik' | 'lainnya';
  urusan: string;
  status: 'draft' | 'diajukan' | 'revisi' | 'terverifikasi';
  opd: OPD;
  skor_klaim: number;
  skor_terverifikasi: number;
  persen_terverifikasi: number;
  layak: boolean;
  diperbarui_pada: string;
}

export interface InovasiDetail extends InovasiRingkas {
  inisiator: string;
  nama_inisiator?: string;
  klasifikasi: string;
  lintang?: number | null;
  bujur?: number | null;
  asta_cita?: string;
  pkpn_klaster?: string;
  pkpn_program?: string;
  mulai_uji_coba?: string | null;
  mulai_penerapan?: string | null;
  pengembangan_terbaru?: string | null;
  rancang_bangun: string;
  tujuan: string;
  manfaat: string;
  hasil: string;
  anggaran?: number | null;
  sumber_anggaran?: string;
  pic_nama?: string;
  pic_kontak?: string;
  catatan_internal?: string;
  catatan_verifikasi?: string;
  diajukan_pada?: string | null;
  diverifikasi_pada?: string | null;
  bisa_diubah: boolean;
  masalah_kelayakan: string[];
  wajib_belum_terisi: string[];
  bukti: NilaiBukti[];
}

export interface NilaiSPD {
  indikator_id: number;
  kode: string;
  variabel: string;
  nama: string;
  bobot: number;
  wajib: boolean;
  parameter_1: string;
  parameter_2: string;
  parameter_3: string;
  pilihan: number;
  skor: number;
  skor_maks: number;
  keterangan: string;
  tautan: string;
  berkas: BerkasFile[];
}

export interface ProyeksiHitungan {
  jumlah_inovasi: number;
  pembagi: number;
  skor_spd: number;
  skor_spd_maks: number;
  rata_kematangan: number;
  skor_jumlah_inovasi: number;
  skor_sid: number;
  skor_total: number;
  indeks: number;
  kategori: string;
  yandas_terpenuhi: number;
  yandas_kurang: number;
  yandas_terisi: string[];
  yandas_kosong: string[];
  kursi_kosong: number;
}

export interface RingkasanStatistik {
  tahun: number;
  total_inovasi: number;
  layak: number;
  menunggu_verifikasi: number;
  terverifikasi: number;
  opd_terlibat: number;
  opd_belum_lapor: number;
  proyeksi_klaim: ProyeksiHitungan;
  proyeksi_terverifikasi: ProyeksiHitungan;
  per_tahapan: { label: string; jumlah: number }[];
  per_bentuk: { label: string; jumlah: number }[];
}

export interface RekapOPD {
  opd: OPD;
  jumlah: number;
  terverifikasi: number;
  layak: number;
  rata_skor_klaim: number;
  rata_skor_terverifikasi: number;
}
