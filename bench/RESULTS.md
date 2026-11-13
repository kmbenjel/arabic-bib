# Head-to-head results

Made by `bench/compare.sh` on a Linux VM (Python 3.12). Every number below comes from a run.

## Versions, install size, dependencies, import time

| library | version | installed size | packages pulled in | import time |
|---|---|---|---|---|
| arabic-bib | 0.1.0 | 1 MB | 0 | 0.091 s |
| PyArabic | 0.6.15 | 1 MB | 2 | 0.019 s |
| CAMeL Tools | 1.6.0 | 5640 MB | 82 | 0.023 s |
| Maha | 0.3.0 | 12 MB | 8 | 0.098 s |
| Tashaphyne | 0.3.6 | 6 MB | 3 | 0.017 s |

## 1. Spelling variants folded to one search key

| variant | arabic-bib | PyArabic | CAMeL Tools | Maha | Tashaphyne |
|---|---|---|---|---|---|
| hamza on alef: «الإمام» = «الامام» | ✓ | ✓ | ✓ | ✓ | ✓ |
| madda: «القرآن» = «القران» | ✓ | ✓ | ✓ | ✓ | ✓ |
| alef wasla: «ٱلرحمن» = «الرحمن» | ✓ | ✓ | ✓ | ✓ | ✗ |
| ta marbuta: «مكتبة» = «مكتبه» | ✓ | ✓ | ✓ | ✓ | ✓ |
| alef maqsura: «مصطفى» = «مصطفي» | ✓ | ✗ | ✓ | ✓ | ✓ |
| hamza on waw: «مسؤول» = «مسوول» | ✓ | ✗ | ✗ | ✓ | ✗ |
| hamza on ya: «رئيس» = «رييس» | ✓ | ✗ | ✗ | ✓ | ✗ |
| diacritics: «مُحَمَّدٌ» = «محمد» | ✓ | ✓ | ✓ | ✓ | ✓ |
| tatweel: «كتــاب» = «كتاب» | ✓ | ✓ | ✗ | ✓ | ✓ |
| presentation forms (PDF text): «ﺟﻬﺎﺩ» = «جهاد» | ✓ | ✗ | ✓ | ✗ | ✗ |
| lam-alef ligature: «ﻻ» = «لا» | ✓ | ✓ | ✓ | ✓ | ✓ |
| Persian ya: «یوسف» = «يوسف» | ✓ | ✗ | ✗ | ✗ | ✗ |
| Persian kaf: «کتاب» = «كتاب» | ✓ | ✗ | ✗ | ✗ | ✗ |
| Arabic-Indic digits: «١٤٢٠» = «1420» | ✓ | ✗ | ✗ | ✓ | ✗ |
| bidi marks: «‏الرسالة‎» = «الرسالة» | ✓ | ✗ | ✗ | ✗ | ✗ |
| **total** | **15/15** | **7/15** | **8/15** | **11/15** | **7/15** |

## 2. Author-name matching (179 labelled pairs, `tests/cases/author_pairs.tsv`)

Labels: same / different / unknown, the decision a careful cataloguer makes from the two strings alone. A false merge is «same» said of two different people.

| method | accuracy | precision of «same» | recall of «same» | false merges |
|---|---|---|---|---|
| **arabic-bib `match_authors`** | **96%** | **99%** | **97%** | **1** |
| arabic-bib + equal after normalising | 27% | 100% | 2% | 0 |
| arabic-bib + words of one ⊂ the other | 59% | 84% | 50% | 1 |
| PyArabic + equal after normalising | 27% | 100% | 2% | 0 |
| PyArabic + words of one ⊂ the other | 58% | 84% | 49% | 1 |
| CAMeL Tools + equal after normalising | 27% | 100% | 2% | 0 |
| CAMeL Tools + words of one ⊂ the other | 58% | 84% | 49% | 1 |
| Maha + equal after normalising | 27% | 100% | 2% | 0 |
| Maha + words of one ⊂ the other | 58% | 84% | 49% | 1 |
| Tashaphyne + equal after normalising | 27% | 100% | 2% | 0 |
| Tashaphyne + words of one ⊂ the other | 58% | 84% | 49% | 1 |

## 3. Bibliographic tasks (closest public function of each library)

| input | arabic-bib | PyArabic | CAMeL Tools | Maha | Tashaphyne |
|---|---|---|---|---|---|
| death: ابن تيمية (ت 728 هـ) | `"ت 728 هـ"` | — | — | `[]` | — |
| death: المتوفى سنة ثمان وعشرين وسبعمائة | `"ت 728 هـ"` | — | — | `[]` | — |
| death: الذهبي (673 - 748 هـ) | `"ت 748 هـ"` | — | — | `[]` | — |
| number: ثمان وعشرين وسبعمائة | `728` | `728` | — | `["728"]` | — |
| ordinal: الحادية عشرة | `11` | — | — | `["11"]` | — |
| edition: الطبعة الأولى، دار الكتب العلمية، بيروت، 1420 هـ - 1999 م | `{"number": 1, "publisher": "دار الكتب العلمية", "city": "بيروت", "hijri": 1420, "gregorian": 1999}` | — | — | — | — |
| hijri: 728-11-20 | `"1328-9-26"` | — | — | — | — |
| author: شيخ الإسلام تقي الدين أبو العباس أحمد بن عبد الحليم بن تيمية الحراني | `{"ism": "أحمد", "kunya": "أبو العباس", "nasab": ["عبد الحليم", "تيمية"], "laqab": ["شيخ الإسلام", "تقي الدين"], "nisba": ["الحراني"]}` | — | — | — | — |
| wasl: الإستغفار والإجتهاد | `"الاستغفار والاجتهاد"` | — | — | — | — |
| filename: ديوان المتنبي: شرح "العكبري"? | `"ديوان المتنبي شرح «العكبري»؟"` | — | — | — | — |

«—» = the library has no function for this task; `[]` = it has one and found nothing.

## arabic-bib's misses on the pair set

| a | b | label | arabic-bib |
|---|---|---|---|
| الشافعي | محمد بن إدريس الشافعي | same | unknown |
| الإمام الشافعي | أبو عبد الله محمد بن إدريس الشافعي المطلبي | same | unknown |
| الشافعي | مالك بن أنس | different | unknown |
| ابن عبد البر القرطبي | أبو عمر يوسف بن عبد الله النمري | unknown | different |
| فخر الدين الرازي | محمد بن عمر بن الحسين الرازي | same | unknown |
| الخطيب البغدادي | أحمد بن علي بن ثابت الخطيب البغدادي | same | unknown |
| الترمذي | الحكيم الترمذي | different | same |
