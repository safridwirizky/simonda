import React from 'react';
import { UserProfile } from '../types';
import { LayoutDashboard, Lightbulb, FileSpreadsheet, BarChart3, LogIn, LogOut, ShieldCheck, User, UserCog } from 'lucide-react';

interface NavbarProps {
  user: UserProfile | null;
  tahun: number | null;
  activeTab: 'dashboard' | 'inovasi' | 'spd' | 'rekap' | 'akun';
  setActiveTab: (tab: 'dashboard' | 'inovasi' | 'spd' | 'rekap' | 'akun') => void;
  onOpenLogin: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  tahun,
  activeTab,
  setActiveTab,
  onOpenLogin,
  onLogout,
}) => {
  return (
    <header className="sticky top-0 z-30 bg-slate-900 text-white shadow-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Brand Logo & Title */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
            <img
              src="/maskot.ico"
              alt="Maskot SIMONDA"
              className="w-10 h-10 rounded-lg object-cover shadow-lg shadow-emerald-500/20"
            />
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-lg tracking-tight text-white">SIMONDA</span>
                {tahun && (
                  <span className="text-xs bg-emerald-500/20 text-emerald-400 font-semibold px-2 py-0.5 rounded border border-emerald-500/30">
                    IGA {tahun}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 font-medium hidden sm:block">
                Kabupaten Rote Ndao &bull; Nusa Tenggara Timur
              </p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1">
            {user && (
              <>
                <button
                  onClick={() => setActiveTab('dashboard')}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
                    activeTab === 'dashboard'
                      ? 'bg-emerald-500 text-slate-950 shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <LayoutDashboard className="w-4 h-4" />
                  <span>Dashboard</span>
                </button>

                <button
                  onClick={() => setActiveTab('inovasi')}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
                    activeTab === 'inovasi'
                      ? 'bg-emerald-500 text-slate-950 shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <Lightbulb className="w-4 h-4" />
                  <span>Inovasi Daerah</span>
                </button>
              </>
            )}

            {user?.bisa_verifikasi && (
              <>
                <button
                  onClick={() => setActiveTab('spd')}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
                    activeTab === 'spd'
                      ? 'bg-emerald-500 text-slate-950 shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <FileSpreadsheet className="w-4 h-4" />
                  <span>SPD Daerah (15)</span>
                </button>

                <button
                  onClick={() => setActiveTab('rekap')}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
                    activeTab === 'rekap'
                      ? 'bg-emerald-500 text-slate-950 shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Rekap OPD</span>
                </button>

                <button
                  onClick={() => setActiveTab('akun')}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
                    activeTab === 'akun'
                      ? 'bg-emerald-500 text-slate-950 shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  <UserCog className="w-4 h-4" />
                  <span>Kelola Akun</span>
                </button>
              </>
            )}
          </nav>

          {/* User Profile & Auth Controls */}
          <div className="flex items-center space-x-3">
            {user ? (
              <div className="flex items-center space-x-3">
                <div className="text-right hidden sm:block">
                  <div className="flex items-center justify-end space-x-1.5 text-xs font-semibold text-white">
                    {user.bisa_verifikasi ? (
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                    ) : (
                      <User className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    <span>{user.nama}</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    {user.opd ? user.opd.singkatan || user.opd.kode : 'Verifikator Pemkab'}
                  </p>
                </div>
                <button
                  onClick={onLogout}
                  title="Keluar Sesi"
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition"
                >
                  <LogOut className="w-3.5 h-3.5 text-rose-400" />
                  <span className="hidden sm:inline">Keluar</span>
                </button>
              </div>
            ) : (
              <button
                onClick={onOpenLogin}
                className="flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-500 hover:bg-emerald-400 text-slate-950 transition shadow-sm"
              >
                <LogIn className="w-4 h-4" />
                <span>Masuk Akun</span>
              </button>
            )}
          </div>

        </div>
      </div>

      {/* Mobile Tab Bar */}
      {user && (
        <div className="md:hidden flex items-center justify-around bg-slate-950 border-t border-slate-800 px-2 py-1.5 text-xs">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex flex-col items-center py-1 px-2 ${
              activeTab === 'dashboard' ? 'text-emerald-400 font-bold' : 'text-slate-400'
            }`}
          >
            <LayoutDashboard className="w-4 h-4 mb-0.5" />
            <span>Dashboard</span>
          </button>
          <button
            onClick={() => setActiveTab('inovasi')}
            className={`flex flex-col items-center py-1 px-2 ${
              activeTab === 'inovasi' ? 'text-emerald-400 font-bold' : 'text-slate-400'
            }`}
          >
            <Lightbulb className="w-4 h-4 mb-0.5" />
            <span>Inovasi</span>
          </button>
          {user.bisa_verifikasi && (
            <>
              <button
                onClick={() => setActiveTab('spd')}
                className={`flex flex-col items-center py-1 px-2 ${
                  activeTab === 'spd' ? 'text-emerald-400 font-bold' : 'text-slate-400'
                }`}
              >
                <FileSpreadsheet className="w-4 h-4 mb-0.5" />
                <span>SPD</span>
              </button>
              <button
                onClick={() => setActiveTab('rekap')}
                className={`flex flex-col items-center py-1 px-2 ${
                  activeTab === 'rekap' ? 'text-emerald-400 font-bold' : 'text-slate-400'
                }`}
              >
                <BarChart3 className="w-4 h-4 mb-0.5" />
                <span>Rekap</span>
              </button>
              <button
                onClick={() => setActiveTab('akun')}
                className={`flex flex-col items-center py-1 px-2 ${
                  activeTab === 'akun' ? 'text-emerald-400 font-bold' : 'text-slate-400'
                }`}
              >
                <UserCog className="w-4 h-4 mb-0.5" />
                <span>Akun</span>
              </button>
            </>
          )}
        </div>
      )}
    </header>
  );
};
