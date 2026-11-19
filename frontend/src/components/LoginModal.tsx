import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { fetchOpsiMasuk, mulaiLoginEsa, type OpsiMasuk } from '../api';

interface LoginModalProps {
  onClose: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
  /** Pesan yang sudah tampil saat modal dibuka, mis. galat dari alur Esa Office. */
  pesanAwal?: string;
}

export const LoginModal: React.FC<LoginModalProps> = ({ onClose, onLogin, pesanAwal = '' }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Cara masuk yang ditawarkan backend; null selama belum terjawab (paling lama 5 detik,
  // setelah itu kembali ke form lokal seperti sebelum ada SSO).
  const [opsi, setOpsi] = useState<OpsiMasuk | null>(null);
  // Bila kata sandi lokal dibatasi untuk administrator, form-nya baru tampil setelah diminta.
  const [tampilkanLokal, setTampilkanLokal] = useState(false);
  const [mengalihkan, setMengalihkan] = useState(false);

  useEffect(() => {
    let batal = false;
    fetchOpsiMasuk().then((o) => {
      if (!batal) setOpsi(o);
    });
    return () => {
      batal = true;
    };
  }, []);

  // Tombol Kembali dari halaman Esa Office memulihkan halaman ini dari cache browser
  // dengan keadaan yang sama; tanpa ini tombolnya tetap macet di "Mengalihkan...".
  useEffect(() => {
    const pulihkan = (e: PageTransitionEvent) => {
      if (e.persisted) setMengalihkan(false);
    };
    window.addEventListener('pageshow', pulihkan);
    return () => window.removeEventListener('pageshow', pulihkan);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onLogin(username, password);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Username atau password salah.');
    } finally {
      setLoading(false);
    }
  };

  const handleEsa = async () => {
    setMengalihkan(true);
    setError('');
    try {
      await mulaiLoginEsa(); // berhasil: browser langsung berpindah halaman
    } catch (err: any) {
      setMengalihkan(false);
      setError(err?.message || 'Tidak dapat memulai masuk lewat Esa Office.');
    }
  };

  const adaEsa = opsi?.esa_office === true;
  // Kata sandi lokal terbuka untuk semua, atau (login_lokal=false) hanya untuk administrator.
  const lokalTerbuka = opsi?.login_lokal !== false;
  const formLokalTampil = opsi !== null && (!adaEsa || lokalTerbuka || tampilkanLokal);
  const pesan = error || pesanAwal;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-5">

        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center space-x-2">
            <img src="/maskot.ico" alt="Maskot SANDO" className="w-6 h-6 rounded object-cover" />
            <h2 className="text-base font-extrabold text-slate-900">Masuk Akun SANDO</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Tutup">
            <X className="w-5 h-5" />
          </button>
        </div>

        {pesan && (
          <div role="alert" className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold rounded-xl">
            {pesan}
          </div>
        )}

        {opsi === null && (
          <p role="status" className="text-xs text-slate-500 text-center py-4">
            Memuat pilihan masuk...
          </p>
        )}

        {adaEsa && (
          <div className="space-y-2">
            <button
              type="button"
              onClick={handleEsa}
              disabled={mengalihkan}
              className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm rounded-xl shadow transition disabled:opacity-60"
            >
              {mengalihkan ? 'Mengalihkan ke Esa Office...' : 'Masuk dengan Esa Office'}
            </button>
            <p className="text-[11px] text-slate-500 text-center">
              Gunakan akun Esa Office Anda. Kata sandi dimasukkan di Esa Office, bukan di SANDO.
            </p>
          </div>
        )}

        {adaEsa && lokalTerbuka && (
          <div className="flex items-center space-x-3 text-[11px] text-slate-400">
            <div className="flex-1 border-t border-slate-200" />
            <span>atau dengan akun lokal</span>
            <div className="flex-1 border-t border-slate-200" />
          </div>
        )}

        {adaEsa && !lokalTerbuka && !tampilkanLokal && (
          <div className="text-center">
            <button
              type="button"
              onClick={() => setTampilkanLokal(true)}
              className="text-[11px] font-semibold text-slate-500 hover:text-slate-700 underline"
            >
              Masuk dengan kata sandi lokal (khusus administrator)
            </button>
          </div>
        )}

        {formLokalTampil && (
          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-bold text-slate-700 mb-1">Username</label>
              <input
                type="text"
                placeholder="Username..."
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500 font-semibold"
                autoFocus={!adaEsa || tampilkanLokal}
                required
              />
            </div>

            <div>
              <label className="block font-bold text-slate-700 mb-1">Kata Sandi</label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className={
                adaEsa
                  ? 'w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-sm rounded-xl border border-slate-200 transition'
                  : 'w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm rounded-xl shadow transition'
              }
            >
              {loading ? 'Memverifikasi...' : 'Masuk Aplikasi'}
            </button>
          </form>
        )}

        {opsi !== null && (
          <p className="text-[11px] text-slate-400 text-center">
            {adaEsa
              ? 'Akun SANDO dibuat otomatis saat Anda pertama kali masuk dengan Esa Office. Kendala masuk? Hubungi administrator (0895-2840-6066).'
              : 'Belum punya akun? Minta administrator membuatkannya (0895-2840-6066).'}
          </p>
        )}

      </div>
    </div>
  );
};
