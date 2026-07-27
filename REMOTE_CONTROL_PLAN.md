# BestHome Monitor Remote Control MVP

Bu sənəd layihənin təhlükəsiz uzaqdan idarəetmə mərhələsini təsvir edir.

## Məqsəd

- Mövcud 0,5 saniyəlik ekran yenilənməsini saxlamaq
- Admin panelindən mouse və klaviatura idarəsi
- Qısamüddətli sessiya tokeni
- Eyni agent üçün yalnız bir aktiv idarəetmə sessiyası
- Agent kompüterində görünən idarəetmə xəbərdarlığı
- Sessiyanı həm paneldən, həm agent tərəfdən dayandırmaq
- Sessiya və komanda audit qeydləri

## MVP məhdudiyyətləri

- Ekran axını hazırkı screenshot mexanizmindən gəlir
- Səs, clipboard, fayl ötürməsi və çox monitor sonrakı mərhələyə saxlanılır
- Windows 7-11 üçün mouse/klaviatura əmrləri Win32 `SendInput` ilə icra olunur
- Agent serverdən komandaları qısa intervalda götürür; ilk mərhələdə əlavə WebSocket asılılığı yoxdur

## Təhlükəsizlik

- Uzaqdan idarəetmə yalnız admin loginindən sonra başlanır
- Sessiya ID-si təsadüfi və qısamüddətlidir
- Agent sorğuları mövcud upload tokeni ilə autentifikasiya olunur
- Komandalar yalnız aktiv sessiyaya və uyğun agentə verilir
- Sessiya bitdikdə gözləyən komandalar ləğv olunur
- Agentdə idarəetmə aktiv olduqda görünən xəbərdarlıq pəncərəsi göstərilir
