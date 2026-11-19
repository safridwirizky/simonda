# SANDO Rote Ndao

Sistem Analisis dan Monitoring Data Inovasi Kabupaten Rote Ndao. Dipakai sepanjang tahun untuk
mengumpulkan inovasi dan mencicil bukti dukungnya, supaya saat window pelaporan
Innovative Government Award (IGA) dibuka, datanya tinggal disalin.

Django 5 + Django Ninja di belakang, React di depan.

---

## Alur kerja

    Operator OPD                  Verifikator (Bapperida)
    ────────────                  ────────────────────────────
    buat inovasi (draft)
    isi bukti 21 indikator
    ajukan  ───────────────────▶  baca, periksa berkas
                                  ├─ kembalikan + catatan ─▶ status "revisi"
                                  └─ terima ──────────────▶ status "terverifikasi"
                                  verifikasi bukti per indikator
                                  ekspor CSV saat window IGA buka

Sistem menghitung **proyeksi Indeks Inovasi Daerah** memakai rumus asli Lampiran I
butir XI.B, dan menampilkannya dalam dua versi:

- **Klaim** — memakai parameter yang dipilih OPD sendiri.
- **Terverifikasi** — hanya nilai yang sudah dibenarkan verifikator, dan hanya
  inovasi yang lolos syarat kelayakan.

Angka kedua yang dibawa ke rapat. Selisihnya menunjukkan OPD mana yang melaporkan
lebih baik daripada kenyataannya.

Struktur penilaian mengikuti Lampiran II:

| Aspek | Isi | Skor maks | Porsi |
|---|---|---|---|
| SPD | 15 indikator daerah, 20 baris skor | 63 | 25,20% |
| SID | 20 indikator per inovasi | 111 | 44,40% |
| Jumlah Inovasi | dihitung otomatis | 76 | 30,40% |
| **Total** | | **250** | **100%** |

Tiap indikator punya tiga parameter. Skor satu baris = bobot x parameter terpilih.

## Lima aturan yang menentukan skor

**Seluruh 6 urusan wajib pelayanan dasar harus terpenuhi.** Kurang satu saja,
Skor Jumlah Inovasi jadi nol — hilang sampai 76 poin atau 30,4% dari skor
maksimum. Beranda menampilkan urusan mana yang masih kosong.

**Pembagi MAX(14, n).** Melaporkan kurang dari 14 inovasi tetap dibagi 14, jadi
rata-rata kematangan ikut turun. Sistem menampilkan berapa "kursi kosong" tersisa.

**Syarat umur inovasi.** Penerapan harus antara 1 Januari 2025 dan 31 Desember
2026, atau ada pengembangan dalam rentang itu. Rancang bangun minimal 300 kata.
Inovasi yang gagal syarat ini ditandai dan tidak ikut diekspor.

**Indikator tanpa bukti dukung tidak menyumbang skor.** Berlaku sama untuk
SPD dan SID: memilih parameter 1–3 tidak langsung terhitung — skor baris itu
tetap nol sampai ada bukti dukungnya (Bapperida untuk SPD, OPD pelapor untuk
SID). Bukti dukung boleh berupa **berkas terunggah atau tautan** — dokumen di
atas 1 MB tidak lolos batas unggah, jadi tautan (mis. Google Drive) dipakai
sebagai gantinya dan tetap membuka skor. `NilaiSPD.skor` dan `NilaiSID.skor`
sama-sama mengecek `daftar_berkas.exists() or tautan` sebelum menghitung
`bobot x pilihan` — satu-satunya titik sumber kebenaran, dipakai baik untuk
baris individual maupun agregat `skor_klaim`/`skor_terverifikasi`. Klaim
tanpa bukti sama sekali tidak boleh memengaruhi proyeksi indeks.

Setiap kali OPD mengubah bukti, status verifikasinya otomatis kembali ke
"menunggu". Bukti lama tidak bisa diam-diam diganti setelah disetujui.

**Format berkas dibatasi per jenis bukti.** SPD selalu PDF. SID juga PDF
secara default, kecuali indikator 35 (Video inovasi daerah) yang hanya
menerima berkas video, dan indikator 25 & 30 (Sosialisasi Inovasi Daerah,
Layanan Terintegrasi) yang menerima PDF maupun gambar (JPG/PNG) — keduanya
lazim berupa tangkapan layar atau foto kegiatan, bukan dokumen resmi.
`iga.ekstensi_sid_diizinkan()` menyimpan pemetaan ini, dipakai endpoint
unggah berkas di `api.py` sebelum berkas disimpan; berkas dengan ekstensi
yang tidak sesuai ditolak (415) sebelum sempat menyentuh penyimpanan.

**Satu indikator boleh punya banyak berkas.** Mengunggah berkas baru menambah
daftar, bukan menimpa berkas sebelumnya — model `BerkasSPD`/`BerkasSID`
menyimpan tiap berkas sebagai baris tersendiri (relasi satu-ke-banyak ke
`NilaiSPD`/`NilaiSID`). Setiap berkas juga bisa dihapus satu per satu; hapus
memanggil `storage.delete()` sungguhan lewat `FileField.delete(save=False)`
sebelum baris databasenya dibuang, jadi tidak ada berkas yang nyangkut tak
terjangkau di R2 seperti pada model lama (satu `FileField` per baris, di mana
unggahan kedua menimpa referensi ke berkas pertama tanpa menghapusnya).

**Indikator 33 (Kemanfaatan Inovasi) punya 6 basis ukur, OPD pilih satu.**
Sesuai Lampiran II butir 33 a–f, ambang parameter 1–3 berbeda tergantung basis
yang dipakai (jumlah penerima manfaat, cakupan unit, efisiensi belanja,
penambahan pendapatan, jumlah produk, atau tren kinerja) — bobot indikatornya
sama (3) untuk semua basis, tapi teks dan ambang parameternya tidak boleh
tercampur. `iga.PARAMETER_KEMANFAATAN` menyimpan keenam set ambang itu;
`NilaiSID.basis_ukur` menyimpan basis mana yang dipilih OPD, dan
`baris_nilai()` di `api.py` menukar `parameter_1/2/3` yang ditampilkan sesuai
basis tersimpan. Memilih parameter 1–3 tanpa memilih basis dulu ditolak API
(400) karena "2" berarti hal yang berbeda di tiap basis.

---

## Memasang

### Backend

Basis data memakai PostgreSQL, termasuk untuk pengembangan lokal (bukan cuma
produksi). Siapkan peran dan basis datanya sekali saja:

```bash
sudo -u postgres psql -c "CREATE ROLE simonda WITH LOGIN PASSWORD 'ganti-ini';"
sudo -u postgres psql -c "CREATE DATABASE simonda WITH OWNER simonda ENCODING 'UTF8';"
```

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cat > .env <<'EOF'
DEBUG=1
SECRET_KEY=ganti-dengan-hasil-perintah-di-bawah
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ORIGINS=http://localhost:5173
DB_NAME=simonda
DB_USER=simonda
DB_PASSWORD=ganti-ini
DB_HOST=localhost
DB_PORT=5432
EOF

python -c "import secrets; print(secrets.token_urlsafe(50))"   # isi SECRET_KEY

python manage.py migrate
python manage.py seed_simonda --tahun 2027    # catat kata sandi yang dicetak
python manage.py runserver
```

Kosongkan blok `DB_*` di `.env` untuk memakai SQLite berkas lokal alih-alih
Postgres — cukup untuk uji coba cepat, tapi jangan dipakai untuk data yang
sungguhan dipakai (lihat catatan di `simonda/settings.py`).

Dokumentasi API otomatis tersedia di `http://localhost:8000/api/docs`.
Django admin di `/admin/` untuk membuat akun operator tiap OPD.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local     # sesuaikan VITE_API_URL bila perlu
npm run dev                    # http://localhost:5173
```

React 18 dan Vite 7, tanpa pustaka UI atau router tambahan. Butuh Node 20.19 ke
atas. Gaya ditulis tangan di `src/index.css` memakai variabel CSS, dan tidak ada
font web supaya tetap terbaca saat jaringan kantor putus.

Bila npm menahan skrip `postinstall` milik esbuild dengan peringatan
`allow-scripts`, biarkan saja. Skrip itu hanya optimasi; binernya sudah datang
lewat paket `@esbuild/*` sesuai platform, dan `npm run dev` maupun
`npm run build` tetap berjalan normal. Membiarkannya tertahan justru pilihan
yang lebih aman.

Untuk produksi, `npm run build` menghasilkan `dist/` yang bisa disajikan Nginx
sebagai berkas statis di depan Gunicorn.

### Uji

```bash
cd backend
export ALLOWED_HOSTS=localhost,127.0.0.1,testserver
python uji_skor.py        # 32 pemeriksaan katalog dan rumus
python uji_alur.py        # 85 pemeriksaan alur kerja
python uji_kontrak.py     # 42 pemeriksaan kontrak API terhadap antarmuka
python uji_rekap_docx.py   # 43 pemeriksaan rekap Word (.docx)
python uji_esa_office.py   # SSO Esa Office (OpenID Connect) terhadap Esa Office tiruan
```

`uji_skor.py` membuktikan ulang angka resmi pedoman dari bobot yang dimasukkan.
`uji_alur.py` menguji isolasi antar OPD, penguncian saat menunggu verifikasi,
pemeriksaan kelayakan, aturan 6 dari 6 urusan, pembagi MAX(14, n), selisih klaim
versus terverifikasi, ekspor CSV, dan alur Kelola Akun OPD (verifikator membuat,
menonaktifkan/mengaktifkan, dan mereset sandi akun operator).
`uji_kontrak.py` memastikan setiap kolom yang dibaca berkas `.jsx` benar-benar
ada di respons API — inilah yang biasanya jebol saat backend diubah tetapi
frontend belum menyusul.
`uji_esa_office.py` menguji masuk lewat Esa Office ([SSO](#sso-dengan-esa-office))
lewat API Django asli terhadap Esa Office tiruan (`uji_idp_palsu.py`, berjalan di
`127.0.0.1` dan menandatangani ID token RS256/ES256 sungguhan): alur
`/auth/esa/mulai` → `/authorize` → `/auth/esa/callback` → `/auth/esa/tukar`, cookie
sesi dan pengikat tiket ke browser, ID token palsu/kedaluwarsa/salah `nonce`,
aturan akun (penautan, peran, OPD, mutasi, akun nonaktif), batasan unik di basis
data, perintah `esa_office_cek`, dan kecocokan migrasi dengan model. Ia hanya
membuat dan menghapus data berawalan `uji_esa_`/`UJIESA` dan mengabaikan setelan
`ESA_OFFICE_*` dari `.env`; jalankan dengan `DEBUG=1 python uji_esa_office.py`
setelah `ALLOWED_HOSTS` di-export seperti di blok di atas (skrip menambahkan
`testserver` sendiri).

Jalankan `uji_alur.py` dan `uji_kontrak.py` dengan basis data segar: keduanya
menghapus seluruh inovasi saat mulai. `uji_esa_office.py` cukup dengan basis data
yang sudah di-migrate dan di-seed.

## Peta antarmuka

| Halaman | Siapa | Isi |
|---|---|---|
| Beranda | semua | Proyeksi indeks, batang komposisi 250 poin, dua aturan penentu |
| Daftar inovasi | semua | Operator hanya melihat OPD sendiri |
| Antrean verifikasi | verifikator | Inovasi berstatus menunggu, dengan lencana jumlah |
| Indikator daerah | verifikator | 20 baris SPD, dikelompokkan per variabel |
| Rekap OPD | verifikator | Rata skor per OPD dan daftar yang belum melapor |
| Kelola Akun | verifikator | Buat, nonaktifkan/aktifkan, dan reset sandi akun operator OPD (membuat akun dan reset sandi ditolak bila `ESA_OFFICE_LOGIN_LOKAL=0`) |

---

## Membuat akun OPD

> Bagian ini untuk login lokal. Bila SSO Esa Office menyala, akun operator
> dibuat otomatis saat pegawai pertama kali masuk lewat Esa Office; lihat
> [SSO dengan Esa Office](#sso-dengan-esa-office).

`seed_simonda` sudah langsung membuat satu akun operator per OPD (username =
kode OPD huruf kecil, sandi awal `admin123` untuk semua — **wajib diganti**
sebelum dipakai sungguhan).

Akun operator baru berikutnya dibuat verifikator sendiri dari dalam SANDO,
lewat menu **Kelola Akun** (bisa buat, lihat daftar, nonaktifkan/aktifkan, dan
reset sandi — tanpa perlu Django Admin). Akun `verifikator`/`admin` baru tetap
lewat `/admin/` → Users → Add, karena itu batas kepercayaan yang lebih tinggi
dan bukan tugas rutin.

| Peran | Bisa apa |
|---|---|
| Operator OPD | Hanya inovasi OPD-nya sendiri. Tidak bisa memverifikasi. |
| Verifikator | Melihat semua OPD, memverifikasi, mengekspor, kelola akun operator. |
| Administrator | Semua di atas, plus Django admin. |

---

## SSO dengan Esa Office

Akun pegawai dipusatkan di **Esa Office**, yang berperan sebagai penyedia identitas
OpenID Connect (OAuth 2.0 *Authorization Code* + PKCE). SANDO adalah klien OIDC
pertamanya. Kata sandi diketik hanya di halaman login Esa Office: SANDO tidak
pernah melihat, meneruskan, atau menyimpannya, dan token Esa Office tidak disimpan.

| | Esa Office | SANDO |
|---|---|---|
| Menjawab | Siapa orang ini: ASN, NIP, nama, perangkat daerah | Apa yang boleh ia lakukan di sini: peran, OPD yang datanya terlihat, akun aktif atau tidak |
| Menyimpan | Akun dan kata sandi | Peran, OPD, dan tautan ke identitas Esa Office (`sub`) |

SSO menyala bila `ESA_OFFICE_ISSUER` diisi di `backend/.env`; dikosongkan, SANDO
memakai login lokal seperti sebelumnya. Login lokal tidak dihapus: SuperUser awal
tetap akun yang disediakan terpisah (`createsuperuser`) dan bisa masuk dengan kata
sandi lokal sebagai cadangan bila Esa Office sedang mati.

> Bagian ini mengandaikan Esa Office sudah menyediakan endpoint OIDC yang
> dijelaskan di [Kontrak untuk Esa Office](#kontrak-untuk-esa-office). Selama itu
> belum ada, biarkan `ESA_OFFICE_ISSUER` kosong.

### Alur

1. Tombol **Masuk dengan Esa Office** membuat `verifier` acak yang disimpan di
   `sessionStorage` tab itu, lalu mengarahkan browser ke
   `GET /api/auth/esa/mulai?tantangan=SHA256(verifier)`.
2. Backend membuat `state`, `nonce`, dan pasangan PKCE (S256), menyimpannya di cookie
   bertanda tangan (`sando_esa`: HttpOnly, SameSite=Lax, Secure di luar mode DEBUG,
   hanya terkirim ke `/api/auth/esa/`, berlaku 10 menit), lalu mengalihkan browser ke
   `authorization_endpoint` Esa Office.
3. Pengguna login di Esa Office, yang mengalihkan browser ke
   `ESA_OFFICE_REDIRECT_URI` (`/api/auth/esa/callback?code=…&state=…`).
4. Backend mencocokkan `state` dengan cookie, menukar `code` di `token_endpoint`
   (client secret + `code_verifier`), lalu memeriksa ID token: tanda tangan lewat
   JWKS, `iss`, `aud`, `exp`, `iat`, dan `nonce`.
5. Backend mencari atau membuat akun SANDO untuk `sub` itu (aturan di bawah),
   menerbitkan tiket sekali pakai (berlaku 60 detik; yang disimpan hanya hash-nya)
   yang terikat ke `tantangan` tadi, lalu mengalihkan browser ke
   `ESA_OFFICE_FRONTEND_URL#esa_tiket=…`. Fragmen URL tidak pernah dikirim ke server
   mana pun.
6. Frontend menukar tiket beserta `verifier` lewat `POST /api/auth/esa/tukar` dan
   menerima JWT SANDO (HS256, 12 jam) yang sama persis dengan hasil login lokal.
   `AuthBearer` dan semua hak akses tidak berubah.

`verifier` di langkah 1 dan 6 menutup *login CSRF*: tanpanya, orang yang punya akun
Esa Office bisa menyelesaikan login di browsernya sendiri lalu mengirim korban
tautan `https://<frontend>/#esa_tiket=…`, dan korban masuk sebagai dirinya.
`verifier` si penyerang tidak ada di browser korban, jadi tiketnya tidak bisa
ditukar (dan satu percobaan salah sudah menghanguskan tiketnya).

| Persyaratan | Penerapan di SANDO |
|---|---|
| HTTPS | Issuer, redirect URI, alamat frontend, dan semua endpoint dari dokumen discovery wajib `https://` (`http` hanya untuk `localhost` saat uji). Alamat yang memuat `#`, spasi, atau `user:sandi@` ditolak. |
| Tanda tangan | Hanya algoritma asimetris (bawaan RS256/ES256). Kunci diambil dari JWKS dan dicocokkan lewat `kid`; `none`, `HS*`, dan kunci `oct` ditolak, dan algoritma ditentukan setelan SANDO, bukan header token. |
| Masa berlaku | `exp` dan `iat` wajib (toleransi selisih jam 60 detik). Tiket SANDO 60 detik sekali pakai; JWT SANDO 12 jam. |
| Klien terdaftar | `client_id` dan `client_secret` dari Esa Office. Rahasia hanya di `.env` server: tidak pernah ke frontend, URL, atau log. |
| `state` | Acak, diikat ke browser lewat cookie; callback tanpa `state` yang cocok ditolak. |
| `nonce` | Acak per login; harus sama dengan klaim `nonce` di ID token. |
| Redirect URI | Selalu dari setelan SANDO (bukan dari permintaan) dan harus persis sama dengan yang didaftarkan di Esa Office. |
| PKCE | S256, `code_verifier` acak per login. |
| `iss` dan `aud` | `iss` harus persis sama dengan `ESA_OFFICE_ISSUER`; `aud` harus memuat `client_id`. |

### Memasang SSO

1. **Daftarkan SANDO di Esa Office** sebagai klien rahasia (*confidential client*):
   `client_id`, `client_secret`, dan satu redirect URI persis
   `https://<backend-sando>/api/auth/esa/callback` (tanpa wildcard).
2. Di server: `pip install -r requirements.txt` (kini memuat `PyJWT[crypto]`), lalu
   `python manage.py migrate` (migrasi `0010_esa_office_oidc`: kolom baru pada OPD dan
   pengguna, serta tabel tiket masuk).
3. Isi `backend/.env`:

   ```bash
   ESA_OFFICE_ISSUER=https://esa-office.rotendaokab.go.id   # contoh; pakai issuer yang sebenarnya
   ESA_OFFICE_CLIENT_ID=sando
   ESA_OFFICE_CLIENT_SECRET=<dari Esa Office; hanya di server>
   ESA_OFFICE_REDIRECT_URI=https://<backend-sando>/api/auth/esa/callback
   ESA_OFFICE_FRONTEND_URL=https://<frontend-sando>
   ```

   `ESA_OFFICE_ISSUER` harus persis sama dengan `issuer` di dokumen discovery Esa Office,
   dan tanpa `#`: bagian alamat setelah `#` (mis. `https://…/#/api/…`) adalah rute halaman
   web yang tidak pernah sampai ke server, jadi bukan alamat API.
4. Jalankan `python manage.py esa_office_cek` **dari server SANDO**. Perintah ini
   memeriksa setelan, dokumen discovery, dan JWKS Esa Office apa adanya (tanpa menulis ke
   basis data dan tanpa menampilkan rahasia), mencetak redirect URI yang harus
   didaftarkan, dan berhenti dengan galat bila ada yang salah. Firewall atau daftar putih
   domain bisa berbeda antara laptop dan server.
5. Coba masuk dengan satu akun nyata sebelum dibuka untuk semua pengguna.

Frontend tidak punya setelan baru: tombol muncul sendiri bila backend melaporkan SSO
menyala (`GET /api/auth/opsi`). Di produksi frontend harus dilayani lewat `https://`:
browser hanya menyediakan Web Crypto (untuk `verifier`) di halaman https atau
`localhost`.

Setelan opsional:

| Variabel | Bawaan | Arti |
|---|---|---|
| `ESA_OFFICE_SCOPE` | `openid profile` | Harus memuat `openid`. |
| `ESA_OFFICE_ALGORITMA` | `RS256,ES256` | Algoritma tanda tangan ID token yang diterima. Hanya yang asimetris (`RS`/`PS`/`ES` 256–512); `HS256` atau `none` ditolak. |
| `ESA_OFFICE_TIMEOUT` | `8` | Detik, untuk tiap panggilan jaringan ke Esa Office. Nilai yang bukan angka positif menghentikan aplikasi dengan pesan yang menyebut nama variabelnya. |
| `ESA_OFFICE_TAUTKAN_NIP` | kosong | NIP verifikator/admin lama yang boleh ditautkan otomatis, dipisah koma (lihat [Aturan akun](#aturan-akun)). |
| `ESA_OFFICE_PETAKAN_OPD_OTOMATIS` | `1` | `0`: OPD hanya dikenali lewat `esa_id` yang diisi admin (lihat [Pemetaan perangkat daerah](#pemetaan-perangkat-daerah)). |
| `ESA_OFFICE_LOGIN_LOKAL` | `1` | `0`: selama SSO menyala, kata sandi lokal hanya berlaku bagi administrator/superuser. Gunakan setelah semua pegawai pindah ke Esa Office. |

### Kontrak untuk Esa Office

Yang SANDO harapkan dari Esa Office. `backend/uji_idp_palsu.py` adalah contoh kecil yang
bisa dijalankan dari perilaku ini (khusus pengujian, bukan untuk produksi).

**Discovery** — `GET {ESA_OFFICE_ISSUER}/.well-known/openid-configuration` berisi
`issuer` (persis sama dengan `ESA_OFFICE_ISSUER`), `authorization_endpoint`,
`token_endpoint`, dan `jwks_uri`, semuanya `https://`; `userinfo_endpoint` opsional.
Bila diiklankan, SANDO memeriksa bahwa `response_types_supported` memuat `code`,
`code_challenge_methods_supported` memuat `S256`, `id_token_signing_alg_values_supported`
beririsan dengan `ESA_OFFICE_ALGORITMA`, dan `token_endpoint_auth_methods_supported`
memuat `client_secret_basic` (dipilih bila ada) atau `client_secret_post`. Bila tidak
diiklankan, SANDO memakai `client_secret_basic` dan tetap mengirim PKCE S256.

**`/authorize`** — Authorization Code. SANDO mengirim `response_type=code`, `client_id`,
`redirect_uri`, `scope`, `state`, `nonce`, `code_challenge`, `code_challenge_method=S256`,
dan `prompt=login` setelah pengguna keluar dari SANDO. Esa Office harus mengautentikasi
pengguna di halamannya sendiri, hanya menerima redirect URI yang terdaftar persis,
mengembalikan `code` dan `state` apa adanya, membalas `error=access_denied` bila
pengguna membatalkan, dan menghormati `prompt=login` (meminta kata sandi lagi walau sesi
Esa Office masih hidup).

**`/token`** — `POST` form-urlencoded: `grant_type=authorization_code`, `code`,
`redirect_uri`, `code_verifier`. Klien mengautentikasi diri dengan header Basic atau
`client_id` dan `client_secret` di badan. Kode berumur pendek dan sekali pakai, PKCE S256
diperiksa di sini, dan kode yang salah/terpakai/kedaluwarsa dijawab
`400 {"error": "invalid_grant"}`. Balasan memuat `id_token` (dan `access_token` bila
`userinfo_endpoint` dipakai).

**ID token** — JWT bertanda tangan RS256 atau ES256 dengan kunci dari `jwks_uri`
(`kid` di header; wajib bila JWKS punya lebih dari satu kunci yang cocok) dan klaim:

| Klaim | Wajib | Dipakai SANDO untuk |
|---|---|---|
| `iss` | ya | Harus persis sama dengan `ESA_OFFICE_ISSUER`. |
| `aud` | ya | Harus memuat `client_id` SANDO (bila lebih dari satu, `azp` harus `client_id`). |
| `exp`, `iat` | ya | Masa berlaku (toleransi jam 60 detik). Buat berumur pendek: ID token hanya dipakai sekali, saat callback. |
| `nonce` | ya | Harus sama dengan nilai yang dikirim SANDO. |
| `sub` | ya | Identitas tetap pengguna di Esa Office: stabil, unik, dan tidak pernah dipakai ulang oleh orang lain (≤ 255 karakter). Satu-satunya kunci penautan akun. |
| `name` | ya | Nama tampil; mengikuti Esa Office di setiap login. |
| `perangkat_daerah.id` | ya | ID perangkat daerah yang stabil (≤ 100 karakter), dipetakan ke OPD SANDO. |
| `perangkat_daerah.name` | disarankan | Dipakai untuk pemasangan pertama ke OPD dan untuk pesan log. |
| `nip` | disarankan | Angka saja (≤ 25 digit). Tanpa NIP, akun hanya bisa ditautkan lewat `sub`. |
| `phone_number`, `email` | opsional | Boleh ada; SANDO tidak membaca dan tidak menyimpannya. |

`name`, `nip`, dan `perangkat_daerah` yang tidak ada di ID token dilengkapi dari
`userinfo_endpoint` bila tersedia (`Authorization: Bearer <access_token>`); `sub` di
sana harus sama dengan ID token, dan klaim di ID token yang menang.

**JWKS** — `jwks_uri` memuat kunci publik RSA atau EC (kunci `oct` diabaikan). SANDO
menyimpannya satu jam dan, bila ada `kid` yang tak dikenal, mengunduh ulang paling
sering sekali per 30 detik, jadi rotasi kunci cukup dengan menerbitkan kunci baru
berikut `kid` baru.

### Aturan akun

| Hal | Perilaku |
|---|---|
| Penautan | Akun SANDO ditautkan ke `sub` Esa Office (kolom `identity_provider` = `esa-office` dan `external_subject`, unik bila terisi), bukan ke nama, NIP, atau telepon. |
| Pengguna baru | Dibuat otomatis saat login pertama sebagai **operator** di OPD hasil pemetaan, tanpa kata sandi lokal. Username = NIP (atau `esa-…` bila NIP kosong atau bentrok). |
| Peran | Tidak pernah datang dari Esa Office. Untuk menaikkan peran, pegawai masuk sekali lalu admin mengubah perannya di `/admin/` → Users. SuperUser awal tetap disediakan terpisah. |
| Akun SANDO lama | Dipakai ulang lewat NIP: akun yang belum punya identitas Esa Office dan `nip`-nya sama persis ditautkan satu kali; seterusnya hanya `sub` yang dipakai. Lebih dari satu akun ber-NIP sama, atau NIP yang sudah ditautkan ke `sub` lain (mis. akun Esa Office dibuat ulang), ditolak (`akun_ganda`) sampai admin membereskannya di `/admin/` (bagian “Identitas Esa Office” pada pengguna). |
| Verifikator/admin/staf lama | Bila punya kata sandi lokal, **tidak** ditautkan otomatis: login ditolak (`belum_ditautkan`) sampai NIP-nya didaftarkan di `ESA_OFFICE_TAUTKAN_NIP`. Daftarkan hanya setelah dipastikan pemilik NIP itu di Esa Office memang pemegang akunnya. Operator lama tidak perlu didaftarkan. |
| Nama dan NIP | Nama mengikuti Esa Office di setiap login; NIP diperbarui bila belum dipakai akun lain. |
| Identitas tak lengkap | Tanpa `name` atau `perangkat_daerah.id`, atau dengan `nip` yang bukan angka: ditolak (`identitas_tidak_lengkap`). |
| Akun dinonaktifkan di SANDO | Ditolak (`akun_nonaktif`); login tidak pernah mengaktifkannya kembali. |
| Login lokal | Bawaan: tetap bisa bagi akun yang punya kata sandi lokal. Dengan `ESA_OFFICE_LOGIN_LOKAL=0`, hanya administrator/superuser; **Kelola Akun** lalu menolak (409) pembuatan akun dan reset sandi, karena kata sandi lokal tidak dipakai lagi (menonaktifkan/mengaktifkan tetap bisa). |
| Catatan | Penautan, pembuatan akun, pemasangan OPD, dan perpindahan OPD tercatat di log aktivitas; login lewat Esa Office diberi keterangan “via Esa Office”. |

### Pemetaan perangkat daerah

`perangkat_daerah.id` dari Esa Office dipetakan ke OPD SANDO lewat kolom **`OPD.esa_id`**
(unik bila terisi; bisa diisi admin di `/admin/` → OPD). Bila belum ada OPD yang memegang
ID itu dan `ESA_OFFICE_PETAKAN_OPD_OTOMATIS=1` (bawaan), SANDO memasangkannya sendiri ke
**tepat satu** OPD aktif yang belum punya `esa_id` dan yang kode, singkatan, atau namanya
sama persis dengan `perangkat_daerah.name` atau ID-nya (huruf besar/kecil, tanda baca, dan
imbuhan “Kabupaten Rote Ndao” diabaikan). Tidak ada tebakan “mirip”: nol atau lebih dari
satu kecocokan berarti perangkat daerah itu tidak dikenal. Pasangan yang sudah terpasang
tidak pernah diubah oleh login (pemekaran atau penggabungan diperbaiki admin di
`/admin/`), dan pemasangan otomatis dicatat di log aktivitas.

Pemasangan otomatis mempercayai pasangan ID–nama yang pertama kali dikirim Esa Office.
Untuk kontrol penuh di produksi, isi `esa_id` semua OPD di `/admin/` lebih dulu, lalu set
`ESA_OFFICE_PETAKAN_OPD_OTOMATIS=0`.

### Mutasi ASN (pindah perangkat daerah)

Esa Office adalah sumber kebenaran tempat tugas; SANDO hanya menyesuaikan akses datanya.

- **Operator mengikuti Esa Office di setiap login.** Bila `perangkat_daerah.id` berubah,
  akun dipindah ke OPD hasil pemetaan yang baru dan perpindahan itu dicatat di log
  aktivitas (“pindah OPD via Esa Office”, `LAMA -> BARU`). Setelahnya operator hanya
  melihat data OPD baru. Inovasi dan berkas lama tetap milik OPD lama, karena data SANDO
  menempel pada OPD, bukan pada orangnya.
- **Perangkat daerah baru yang belum dikenal SANDO = login ditolak**
  (`opd_tidak_dikenal`), bukan dibiarkan di OPD lama: operator yang sudah pindah tidak
  boleh terus melihat data OPD asalnya. Admin memasangkan OPD barunya (isi `esa_id` di
  `/admin/` → OPD), lalu pegawai mencoba lagi.
- **Verifikator dan admin tidak dipindahkan** (mereka melihat semua OPD), dan
  perangkat daerah yang tak dikenal tidak menghalangi mereka masuk. OPD dari Esa Office
  hanya diisikan bila akunnya belum punya OPD.
- **Berlaku di login berikutnya.** SANDO baru tahu pegawai itu pindah saat ia masuk lagi
  lewat Esa Office; sampai itu, ia masih memakai OPD lama. Untuk pemindahan yang
  mendesak, nonaktifkan akunnya atau ubah OPD-nya di `/admin/` (untuk operator, nilai itu
  ditimpa lagi oleh Esa Office saat login berikutnya).

### Bila pegawai gagal masuk

Layar login hanya menampilkan pesan tetap yang dipilih frontend dari kode di bawah;
isi alamat tidak pernah ditampilkan. Alasan rinci ada di log server (logger
`inovasi.esa_office`; di PythonAnywhere: error log aplikasi web).

| Kode | Biasanya karena | Tindakan |
|---|---|---|
| `dibatalkan` | Pengguna menekan batal di Esa Office. | — |
| `kedaluwarsa` | Login lebih dari 10 menit, cookie diblokir, callback dibuka di browser lain, dua login dimulai bersamaan di browser yang sama (cookie saling menimpa), atau kode otorisasi sudah terpakai. | Ulangi dari tombol Masuk. |
| `tiket` | Tiket sudah terpakai/kedaluwarsa, atau bukan dari tab ini. | Ulangi dari tombol Masuk, di tab yang sama. |
| `tidak_tersedia` | Esa Office mati/lambat, domainnya belum ada di daftar putih PythonAnywhere, atau setelan salah. | `python manage.py esa_office_cek`, lalu periksa log. |
| `opd_tidak_dikenal` | Perangkat daerahnya belum dipetakan ke OPD. | Isi `esa_id` OPD-nya di `/admin/`. |
| `akun_nonaktif` | Akun SANDO-nya dinonaktifkan. | Aktifkan bila memang sah. |
| `belum_ditautkan` | Akun verifikator/admin lama dengan kata sandi lokal. | Daftarkan NIP-nya di `ESA_OFFICE_TAUTKAN_NIP`. |
| `identitas_tidak_lengkap` | Esa Office tidak mengirim `name`, `perangkat_daerah.id`, atau `nip` yang wajar. | Lengkapi data di Esa Office. |
| `akun_ganda` | NIP sama di beberapa akun SANDO, atau sudah ditautkan ke `sub` lain. | Bereskan di `/admin/` → Users. |
| `gagal` | Lainnya (termasuk ID token ditolak atau galat tak terduga). | Lihat log server. |

### Batasan yang perlu diketahui

- **Pencabutan tidak seketika.** JWT SANDO tetap sah sampai 12 jam setelah akses pegawai
  dicabut di Esa Office. Untuk memutusnya segera, nonaktifkan akunnya di SANDO
  (`AuthBearer` menolak token akun nonaktif pada permintaan berikutnya).
- **Keluar belum terpusat.** Keluar dari SANDO hanya mengakhiri sesi SANDO; sesi di Esa
  Office tetap hidup (endpoint `/logout` Esa Office belum dipakai). Supaya komputer
  bersama aman, login Esa Office berikutnya di browser itu otomatis memakai
  `prompt=login`.
- **Login harus selesai di tab yang sama.** `verifier` ada di `sessionStorage` tab yang
  memulai login; membuka tautan callback di browser atau tab lain berakhir di galat
  `tiket`. Mulai ulang saja.
- **Unik NIP dicek saat login, bukan oleh basis data**, karena kolom `nip` lama boleh
  kosong atau kembar. Batasan unik yang ditegakkan basis data adalah `esa_id` dan pasangan
  (`identity_provider`, `external_subject`) (bersyarat; didukung PostgreSQL dan SQLite).
- **Cache per proses.** Dokumen discovery dan JWKS disimpan satu jam per proses (kegagalan
  discovery diingat 15 detik); PythonAnywhere menjalankan beberapa worker, jadi tiap
  worker mengunduh sendiri.
- **PythonAnywhere Free** hanya mengizinkan domain di daftar putih; lihat
  [Yang perlu diketahui soal tier gratis](#yang-perlu-diketahui-soal-tier-gratis).
- **Aplikasi daerah lain.** Esa Office dimaksudkan menjadi SSO terpusat bagi semua
  aplikasi pemerintah daerah: tiap aplikasi mendaftar sebagai klien sendiri (`client_id`,
  rahasia, dan redirect URI sendiri) dan menentukan sendiri peran serta izinnya.
  Kontrak di atas tidak perlu berubah.

---

## Sebelum dipakai sungguhan

**Katalog indikator** diambil dari Lampiran II Surat Kepala BSKDN Nomor
400.10.11/1887/BSKDN tanggal 29 April 2026, tersimpan di `inovasi/iga.py`.
`uji_skor.py` memverifikasinya terhadap angka yang disebut pedoman sendiri
(63 / 111 / 76 / 250 dan proporsi 25,20% / 44,40% / 30,40%). Jalankan uji itu
setiap kali katalog disunting.

Sistem ini sudah dikonfigurasi untuk tahun 2027 (`PEMBAGI_MINIMAL=14`,
`MIN_URUSAN_YANDAS=6` — seluruh 6 urusan yandas wajib terpenuhi, tidak ada
slack). Untuk tahun berikutnya, ubah dua konstanta itu di `iga.py` sesuai tabel
prognosis: pembagi 16 pada 2028, 18 pada 2029.

**Daftar OPD** di `seed_simonda.py` sudah memuat 45 perangkat daerah Rote Ndao.
Cek ulang terhadap Perda SOTK yang berlaku bila ada pemekaran/penggabungan OPD
setelahnya.

**Ganti SECRET_KEY** dan kata sandi administrator hasil seed.

---

## Menaikkan ke produksi (VPS / server sendiri)

```bash
DEBUG=0
SECRET_KEY=<acak, 50 karakter>
ALLOWED_HOSTS=inovasi.rotendaokab.go.id
CSRF_ORIGINS=https://inovasi.rotendaokab.go.id
CORS_ORIGINS=https://inovasi.rotendaokab.go.id
DB_NAME=simonda
DB_USER=simonda
DB_PASSWORD=<acak>
DB_HOST=localhost
```

```bash
python manage.py collectstatic --noinput
gunicorn simonda.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

Taruh Nginx di depan sebagai reverse proxy dengan sertifikat HTTPS. Saat `DEBUG=0`,
HSTS, cookie aman, dan pengalihan SSL menyala sendiri.

Berkas bukti dukung disimpan di `backend/media/`. Folder ini **tidak** ikut dalam
`collectstatic` dan wajib masuk jadwal backup — isinya SK, laporan, dan foto
kegiatan yang tidak ada salinannya di tempat lain. Backup basis data saja tidak cukup.

Simpan juga `LogAktivitas` (jejak audit) minimal satu siklus penilaian penuh.

---

## Deploy gratis (PythonAnywhere + SQLite + R2 + Cloudflare Pages)

Susunan tanpa server sendiri, semua di tier gratis:

| Bagian | Layanan | Peran |
|---|---|---|
| Backend | [PythonAnywhere](https://www.pythonanywhere.com) | Web app Python (WSGI), konfigurasi manual lewat dashboard |
| Basis data | SQLite | Berkas `backend/db.sqlite3` di disk PythonAnywhere (persisten, bukan Postgres/Neon) |
| Berkas bukti dukung | [Cloudflare R2](https://www.cloudflare.com/products/r2/) | Pengganti `backend/media/`, wajib (lihat catatan di bawah) |
| Frontend | [Cloudflare Pages](https://pages.cloudflare.com) | Hosting statis hasil `npm run build` |

Kenapa berkas **wajib** pindah ke R2 walau disk PythonAnywhere sendiri
persisten (beda dari Render): karena frontend (Cloudflare Pages) dan backend
(PythonAnywhere) tetap dua domain berbeda, tautan berkas harus berupa URL
utuh (R2 memberi ini otomatis lewat `S3Storage`), bukan path relatif
`/media/...` yang cuma benar kalau frontend-backend satu server.

`simonda/settings.py` sudah dirancang fleksibel: tanpa `DATABASE_URL` atau
`DB_NAME` di `.env`, otomatis jatuh ke SQLite — tidak ada kode yang perlu
diubah untuk susunan ini.

### Urutan setup

**1. Cloudflare R2** — buat bucket, buat R2 API token (catat *Access Key ID*
dan *Secret Access Key*), catat *Account ID* kamu (untuk menyusun
`R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com`).

**2. PythonAnywhere** — daftar akun gratis, lalu di tab **Consoles**, buka
**Bash console** dan jalankan:

```bash
git clone <url-repo-ini>
cd simonda/backend
python3.12 -m venv ~/.virtualenvs/simonda-venv
source ~/.virtualenvs/simonda-venv/bin/activate
pip install -r requirements.txt
```

Buat `backend/.env` langsung di server (lewat `nano .env` di console, atau
tab **Files**) — **ini file produksi, bukan salinan dari laptop**:

```
DEBUG=0
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(50))">
ALLOWED_HOSTS=<username>.pythonanywhere.com
CORS_ORIGINS=https://simonda-xxxx.pages.dev
CSRF_ORIGINS=https://simonda-xxxx.pages.dev

DATABASE_URL=
DB_NAME=

R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
```
`DATABASE_URL` dan `DB_NAME` sengaja dikosongkan (baris boleh ada, isinya
kosong) supaya jatuh ke SQLite. `CORS_ORIGINS`/`CSRF_ORIGINS` bisa diisi
sementara, diupdate lagi setelah langkah 4 selesai dan domain Cloudflare
Pages-nya diketahui.

Masih di console yang sama, siapkan basis data:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_simonda --tahun 2027
```

**3. Konfigurasi Web app** — di tab **Web**, klik **Add a new web app** →
**Manual configuration** → pilih versi Python yang sama dengan venv di atas.
Isi:
- **Source code**: `/home/<username>/simonda/backend`
- **Virtualenv**: `/home/<username>/.virtualenvs/simonda-venv`
- **WSGI configuration file**: klik link-nya, ganti seluruh isinya jadi:
  ```python
  import os
  import sys

  path = '/home/<username>/simonda/backend'
  if path not in sys.path:
      sys.path.insert(0, path)

  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simonda.settings')

  from django.core.wsgi import get_wsgi_application
  application = get_wsgi_application()
  ```

  **Soal proses web app tidak mewarisi env var dari console**: benar, dan
  memang **tidak perlu** ditambal manual di berkas WSGI ini — `settings.py`
  proyek ini sudah memanggil `load_dotenv(BASE_DIR / ".env")` di baris
  paling atas, dan itu jalan otomatis begitu `get_wsgi_application()` di
  atas mengimpor `simonda.settings`, apa pun yang memicunya (WSGI atau
  console). Syaratnya cuma satu: berkas `backend/.env` dari langkah 2
  harus ada persis di `/home/<username>/simonda/backend/.env` di server —
  bukan soal kode WSGI-nya.

Klik tombol hijau **Reload** di atas tab Web. Catat URL-nya
(`https://<username>.pythonanywhere.com`).

**4. Cloudflare Pages** — hubungkan repo yang sama. Root directory `frontend`,
framework preset **Vite**, build command `npm run build`, output directory
`dist`. Isi environment variable `VITE_API_URL` = URL PythonAnywhere dari
langkah 3 (Vite membakukan env var ini saat *build*, jadi harus diisi di
sini, bukan cuma di `.env` lokal). Deploy, catat domain Pages-nya.

**5. Kembali ke PythonAnywhere** — update `CORS_ORIGINS`/`CSRF_ORIGINS` di
`backend/.env` dengan domain Cloudflare Pages dari langkah 4, lalu klik
**Reload** lagi di tab Web.

### Yang perlu diketahui soal tier gratis

**Whitelist domain luar**: PythonAnywhere Free membatasi domain yang boleh
diakses server. R2 sudah dikonfirmasi bisa diakses dari console pada akun
ini — kalau suatu saat berhenti bisa diakses, cek
`https://www.pythonanywhere.com/whitelist/`.

Bila memakai [SSO Esa Office](#sso-dengan-esa-office), host `ESA_OFFICE_ISSUER` (dan host
endpoint lain yang disebut dokumen discovery-nya, bila berbeda) juga harus ada di
daftar putih itu: SANDO mengambil discovery, JWKS, dan token dari server, bukan dari
browser. Bila tidak, tombol Masuk dengan Esa Office berakhir di pesan “Esa Office sedang
tidak dapat dihubungi”. `python manage.py esa_office_cek` di Bash console memastikannya.

**Tidak ada auto-deploy**: push ke GitHub tidak otomatis ter-deploy. Tiap
ada perubahan kode: `git pull` lewat Bash console, lalu klik **Reload** di
tab Web.

**SQLite tanggung jawab backup sendiri**: beda dari basis data terkelola,
tidak ada *point-in-time recovery* otomatis. `backend/db.sqlite3` harus masuk
jadwal backup manual (unduh lewat tab **Files**, atau salin berkala) —
persis seperti catatan lama soal `backend/media/` di bagian VPS di atas,
sekarang berlaku juga untuk basis datanya.

**Konkurensi tulis SQLite terbatas** (penguncian tingkat berkas) — wajar
untuk jumlah operator OPD yang realistis di sistem ini, tapi bukan pilihan
untuk trafik tulis tinggi bersamaan.
