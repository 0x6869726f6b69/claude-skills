# 英文校正チェックリスト

**出典**：Linda Olson, *Guide to Academic and Scientific Publication: How To Get Your Writing Published in Scholarly Journals*（Proof-Reading-Service.com, 2014）。<https://mail.proof-reading-service.org/e-academia.net/guide/files/inc/8de93e20e8.pdf>
主に Part II（第3〜5章）と第6.2節の内容を、校正で使えるチェック項目として要約・再構成した。「§」はガイドの節番号。例文はこのチェックリストのために作ったもので、ガイドからの引用ではない。
E 群（英文法）と X（組版・抽出）は、ガイドが詳しく扱っていない一般的な校正項目で、非ネイティブ（特に日本語話者）の英語論文に多い誤りを補ったもの。

目次：0 基本姿勢 / 重大度 / G 投稿規定と一貫性 / S 構成 / V 綴りの種類 / A 略語 / P 句読点 / W 語彙・語法 / T 動詞 / R 代名詞 / F 図表 / C 引用・文献 / K タイトル・要旨・キーワード / L 論理の明確さ / E 英文法 / X 指摘しないもの

---

## 0. 校正の基本姿勢（ガイド全体から）

- **正確さと一貫性**（§3, §5.2.3）：ガイドが繰り返す要点。多くの表記はどちらでも正しいが、一つの論文の中で混在すれば誤りになる。迷う表記は `style_sheet.md` に決定を書き、論文全体をそれに合わせる。
- **投稿規定が最優先**（§3）：規定がある項目は、理由があっても規定どおりにする。規定の文章自体の表記（e-mail か email か）も手がかりになる。規定の中で揺れていれば、その誌の既刊論文を見て決め、決めたら統一する。
- **読者の立場で読む**（§4.4.3）：著者には自明でも、初めて読む人には分からない箇所を探す。未定義の略語、指すものが曖昧な代名詞、比較の片方が欠けた文など。
- **意味を変えない**：校正者は著者の主張・データ・用語の意味を変えない。意味が二通りに読める、数値が食い違う、といった校正者だけでは決められない点は「著者確認（query）」にして案を添える。ガイドの PRS Tip にあるとおり、校正者は欄外のコメントで著者と対話する。
- **自動書式を疑う**（§5.3）：自動の番号付け、脚注、文献管理ソフトの出力は誤りを含みやすい。番号の飛び・重複、一部の文献だけ書式が違う、などを確認する。

## 重大度（severity）

| severity | 意味 | 例 | ループの収束判定 |
|---|---|---|---|
| `error`（誤り） | 規則上の誤り、論文内の不統一、投稿規定違反 | 冠詞の欠落、主語と動詞の不一致、未定義の略語、US/UK の混在、本文と文献リストの年の不一致 | 数える |
| `clarity`（明確さ） | 文法的には成り立つが、曖昧・誤読される・読みにくい | 先行詞が不明な it、比較の対象が欠けた文、名詞の積み重ね、50語の文 | 数える |
| `style`（文体） | 好みや磨き上げ。直せば良くなるが、直さなくても誤りではない | 接続語の単調さ、受動態の多用、分割不定詞 | 数えない |
| `query`（著者確認） | 校正者だけでは直せない。著者の判断や知識が要る | 要旨と結果で人数が違う、どちらの意味か決められない文、出典が必要そうな主張 | 数えない（著者へ回す） |

迷ったら：規則違反なら error、読者が誤解しうるなら clarity、好みにすぎないなら style、意味の決定が要るなら query。

---

## G 投稿規定と全体の一貫性（§3, §5.3）

- **G1 投稿規定**：語数・文字数の上限、見出しの書式と語、節番号の有無と書式、要旨の構成、キーワード数、引用方式、図表の位置などが規定と違う。規定が分からなければ G1 は使わず G2 で判断する。〔error〕
- **G2 表記の一貫性**：同じ種類の表記の揺れ。e-mail / email、dataset / data set、見出しの大文字化、日付、単位の書き方など。style sheet に決定を書き、全箇所を合わせる。〔error〕
- **G3 自動書式・参照の不具合**：節番号やリスト番号の飛び・重複、相互参照の番号違い、LaTeX の `??`、脚注の欠落や番号ずれ、脚注だけ違うフォント。〔error〕

## S 構成：見出し・段落・リスト（§3.1, §3.2）

- **S1 見出しの階層**：同じレベルの見出しは同じ書式（太字・斜体・大きさ・大文字化）にし、書式で階層が判別できるようにする。本文を挟まずに同じレベルの見出しが2つ続く、規定にない階層が突然現れる、などは構成の誤読を招く。〔error〕
- **S2 節番号と相互参照**：番号の書式（`1.` / `1.1` / `1.1.1`、番号の後の記号）を統一し、飛びや重複をなくす。本文で節を参照するときは番号を使い、番号がなければ見出しの文言を正確に使う。〔error〕
- **S3 見出しの略語**：定義済みでも見出しには略語を避ける。DNA、IQ のように正式名称より通用している語は可。〔style。規定で禁止なら error〕
- **S4 段落の組み立て**：1段落1話題。冒頭の文で話題を示し、続く文で展開し、最後の文で締めて次へつなぐ。特別な理由のない1文だけの段落（結果を1文ずつ段落にする等）は、同じ種類のものをまとめる。逆に、複数の話題が混ざった長い段落は分ける。構成を大きく変える提案なので、どう分ける・まとめるかを具体的に示す。〔clarity〕
- **S5 段落のつなぎ**：話題・対象とする研究・比較の向きが変わるときは、接続の語句で明示する。段落を It / This / They / These（＋動詞）で始めず、名詞句で主題を言い直す。例：*This shows that …* → *This reduction in latency shows that …*〔clarity〕
- **S6 リスト**：導入の文とコロンで始める（*Three criteria were used:*）。項目の文法形を揃える（*collecting data / analysing results / reporting findings* — 名詞句・動名詞・不定詞を混ぜない）。リスト全体で1文になるなら、その文として文法的に正しく、項目末の句読点も一貫させる。長い項目は完全な文にする。〔並列の崩れ・文法は error、それ以外は clarity〕

## V 綴りの種類（§4.1）

- **V1 US / UK の統一**：どちらでもよいが混在は不可。主な違い：
  - -our / -or（behaviour / behavior）、-re / -er（centre / center）
  - 子音の重ね（modelling / modeling、labelled / labeled、focussed / focused ※ focused は UK でも普通）
  - -ise / -ize（analyse / analyze、organisation / organization）。-ize は UK でも許容される（Oxford spelling）ので、-ise/-ize は「論文内で統一されているか」で判断する
  - ae・oe / e（paediatric / pediatric、oestrogen / estrogen）、-ogue / -og、-ence / -ense（defence / defense）、その他（grey / gray、whilst、amongst、judgement / judgment）
  - 固有名詞・引用文・文献のタイトルは原典の綴りのまま（"World Health Organization" は UK 論文でも z）
  - 規定があれば規定どおり。なければ多数派（`scan.md` の集計）に揃える。指摘は `scope: global` の1件＋各箇所の個別項目にする。〔error〕
- **V2 綴りの揺れ**：同じ語の綴りが論文内で揺れている（acknowledgement / acknowledgment など）。スペルチェッカーは言語設定次第で見落とす。〔error〕

## A 略語（§4.2, §5.1, §6.2）

- **A1 単位の略号**：標準の略号を、同じものは同じ形で使う（ms と msec を混ぜない）。標準単位は定義不要。数値と単位の間の空白（`5 ms` / `5ms`）、% の前の空白も統一する（一般には `5 ms`、`5%`）。〔error〕
- **A2 ラテン語略語**：e.g.、i.e.、cf.、etc.、vs.、viz. は原則カッコの中だけで使い、本文の文の中では書き下す（for example、that is、compare）。句読点（e.g. と i.e. にはピリオド2つ。後ろのコンマの有無は style sheet で統一）。規定がなければイタリックにしない。意味の誤用に注意：cf. は「比較せよ」であって「参照せよ（see）」ではない。i.e.（言い換え）と e.g.（例示）の取り違え。*such as A, B, etc.* は such as と etc. の重複。〔誤用・句読点は error、本文中での使用は style〕
- **A3 et al. など**：et は完全な語なのでピリオドを付けず、al. には付ける（*et. al*、*et al* は誤り。規定がピリオドなしを求める場合を除く）。et al. は本文の文中でも使ってよい唯一のラテン語略語。何人から et al. にするかは引用方式による（C2）。ibid. や idem は指す文献が曖昧になるなら使わない。loc. cit.、op. cit. は避ける。〔error〕
- **A4 略語の定義**：初出で正式名称の後にカッコで示す（*the root mean square error (RMSE)*）。カッコの位置は略語が表す範囲に合わせる：*the root mean square error (RMSE) value* が正しく、*the root mean square error value (RMSE)* では RMSE が value まで含むことになる。定義前の使用・定義なしの使用は誤り。要旨は独立に読まれるので、要旨で定義しても本文の初出で改めて定義する。図表でも改めて定義する（F1）。著者が毎日使っている中心的な略語ほど定義を忘れやすい（ガイドの PRS Tip）。DNA、IQ のように一般に通用する略語は不要。〔error〕
- **A5 略語の運用**：定義したら以後は略語に統一する（正式名称に戻らない。多くの規定が求める）。1〜2回しか使わない略語は定義せず書き下す。定義だけして使わない略語は削る。複数形は s を付け、定義も複数形で書く（*convolutional neural networks (CNNs)*）。動詞・冠詞を合わせる（*the CNNs were*、*an SVM*、*a URL*）。〔定義前使用などは error、1回だけの略語は style〕
- **A6 タイトル・要旨・見出しの略語**：タイトルと見出しでは避ける（通用度の高いもの以外）。要旨では最小限にし、使うなら要旨の中で定義する。〔規定で禁止なら error、それ以外は style〕

## P 句読点（§4.3, §5.2.1）

- **P1 連続コンマ**（*A, B, and C* / *A, B and C*）：どちらでもよいが統一する。規定があれば規定どおり。統一ルールから外すのは誤読を避けるときだけ。〔error〕
- **P2 導入の節・句の後のコンマ**：文頭の従属節や長い導入句の後にはコンマ（*Although the model converged, …*、*According to Tanaka (2019), …*）。短い句（*In 2020 the …*）は省いてもよい。〔長い節は error、短い句は style〕
- **P3 コロンとセミコロン**：コロンは、完結した文を受けて例・列挙・説明を導く（前が完結した文であること：*The parameters were: a and b* は誤り → *Two parameters were used: a and b.*）。セミコロンは、独立した2つの文をつなぐ「大きなコンマ」、または内部にコンマを含む列挙の区切り。両者を取り違えない。コンマだけで2文をつなぐのは誤り（E6）。〔error〕
- **P4 ハイフン**：名詞の前の複合形容詞はハイフンでつなぐ（*a well-known method*、*a two-stage model*、*state-of-the-art results*）が、述語の位置では付けない（*the method is well known*）。-ly 副詞＋形容詞には付けない（*a highly accurate model*）。接頭辞は、母音が重なる（re-establish）、付けないと意味が変わる（re-cover と recover）、次が大文字や数字（non-English、pre-2000）のときにハイフン。それ以外（nonlinear / non-linear など）は辞書・規定に従って統一する。〔統一・名詞の前は error、それ以外は style〕
- **P5 アポストロフィと所有格**：単数 *student's*、複数 *students'*、不規則な複数 *children's*。*it's*（= it is）と *its* の取り違え。所有格を重ねない：*the patients' families' responses* → *the responses of the patients' families*。〔error / 重ねは style〕
- **P6 引用・脚注・引用符と句読点の位置**：著者年方式のカッコ引用は文末のピリオドの前（*… (Smith, 2020).*）。脚注番号はピリオド・コンマの後、コロン・セミコロンの前（番号方式の上付き番号も通常同じ。規定に従う）。引用符とピリオド・コンマの位置（US：内側 *"…data."*、UK：外側 *"…data".*）を統一する。引用の直後に出典が続くときは、文末記号を出典の後に置く。LaTeX で `"` を使うと開き引用符が閉じ引用符の形になる（”word”）ので ``` ``…'' ``` に直す。〔error〕
- **P7 ダッシュと範囲**：数値・ページの範囲は en dash（10–20、pp. 33–41）かハイフンのどちらかに統一し、前後に空白を入れない。挿入句のダッシュの書き方（— か、空白付きの –）も統一。LaTeX では `--` と `---`。〔error〕
- **P8 空白・記号**：句読点の前の空白（*word ,*）、句読点の後の空白の欠落（*word,word*、*Fig.2*）、カッコの対応、全角記号の混入（，．（）：）、ピリオドの重複。〔error〕

## W 語彙・語法（§4.4.1, §1.2）

- **W1 形式性**：短縮形を使わない（*don't* → *do not*、*it's* → *it is*。アポストロフィを検索する）。口語的な語（*a lot of*、*big*、*get*、*thing*、*really*、*pretty*、*kind of*、*and so on*）は正式な語に（*many / much*、*large / substantial*、*obtain / become*、*factor / aspect*）。文頭の *And / But / So / Also* は避ける（*In addition, …*、*However, …*、*Therefore, …*）。感嘆符や修辞疑問も避ける。〔短縮形は error、口語は style〕
- **W2 正確さ・比較**：比較は同じ種類のものどうしで行う（*the accuracy of model A was higher than model B* → *… than that of model B*）。比較の両側を明示する（*higher*—何より？）。言い換えや省略で情報が落ちていないか（どの群か、どの条件か）。結果を述べるとき、*the former / the latter* や代名詞で言い換えるより名詞を繰り返す方が明確（§1.2）。〔clarity。比較の対象の誤りは error〕
- **W3 用語の一貫性**：中核の概念・群・条件・尺度・質問紙の呼び方は最後まで同じにする（*control group* を途中から *baseline group* と呼ばない。*Questionnaire 2* を *the second survey* と呼ばない）。単調さを避ける言い換え（W5）は一般語に限り、専門用語や定義した用語には使わない。大文字化の揺れ（*Federated Learning* / *federated learning*）。成人を *girls / boys* と呼ばない（*women / men*、*female / male participants*）。〔error〕
- **W4 専門用語と名詞の連続**：読者が知らないかもしれない用語は初出で説明する。専門用語を並べて説明の代わりにしない。名詞を何個も積み重ねた句は前置詞で分解する：*a low-resource language speech recognition error analysis* → *an analysis of speech recognition errors in low-resource languages*。〔clarity〕
- **W5 語の変化と反復**：同じ接続語（*However*、*Moreover*、*In addition*）や報告動詞（*show*）で文を始め続けない。*however / yet / nevertheless*、*show / reveal / indicate / suggest*、*particularly / especially* などを使い分ける。ただし報告動詞は証拠の強さが違う（show ＞ indicate ＞ suggest）ので、強さが変わる言い換えは query にする。〔style〕
- **W6 数の書き方**：文頭に数字を置かない（*12 samples were* → *Twelve samples were*、または語順を変える）。単位を伴う数は数字（*3 mm*）。それ以外は 1〜9 を語、10 以上を数字にするのが一般的だが、分野や規定で異なる。規定がなければ論文内で統一する（*three trials* と *4 trials* の混在は誤り）。序数も同様（*third*、*12th*）。小数点はピリオド、3桁区切りはコンマ（1,389.09。1.389,09 は誤り）。〔error〕
- **W7 人の呼び方**：研究参加者を病名で呼ばない（*diabetics* → *patients with diabetes*）。特に初出で。*subjects / participants* は規定に従う。人を *it* や *that* で受けない（*the participant that* → *the participant who*）。〔規定違反は error、それ以外は style〕

## T 動詞：時制・態・不定詞（§4.4.2）

- **T1 先行研究の時制**：文献が論じている・示している内容は現在形（*Smith (2015) argues that …*）。特定の研究で行ったことは過去形（*Smith (2015) surveyed 300 farmers*）。研究の流れ・傾向は現在完了（*Several studies have examined …*）。時期の違う研究を対比するなら使い分けてよい。〔段落内の無秩序な混在は error、それ以外は style〕
- **T2 本研究の時制**：方法・結果は過去形（*We collected …*、*Accuracy increased …*）。論文自体・図表・一般的な事実は現在形（*Table 2 shows …*、*This paper proposes …*）。同じ段落の中で理由なく時制を変えない。〔error〕
- **T3 受動態**：誤りではないが、誰が行ったのか（著者自身か、引用すべき第三者か）が曖昧になる。行為者が重要なら能動態にする（*It was found that …* → *We found that …*）。要旨では能動態を求める規定もある。〔style。行為者が曖昧で誤解を招くなら clarity〕
- **T4 分割不定詞**：ガイドは *to* と動詞の間に副詞を入れない立場（*to accurately estimate* → *to estimate accurately*）。ただし現在の多くのスタイルガイド（Chicago など）は許容するので、規定が禁止していなければ style 扱い。直すと不自然になるなら残す。〔style〕

## R 代名詞と人称（§4.4.3, §3.2.1）

- **R1 先行詞の明確さ**：it、this、they、them、which が何を指すか一つに決まるか。候補が2つ以上あれば名詞で言い直す（*The server sends the model to the client, and it updates it.* → *…, and the client updates the model.*）。1文に代名詞が多すぎないか。単独の *This* ＋動詞（*This suggests*）は *This result suggests* に。〔clarity〕
- **R2 数の一致**：複数のものを it で、単数のものを they で受けていないか。*data* の単複（*data are / data is*）は style sheet で統一する。〔error〕
- **R3 I / we**：単著は I、共著は we（混在は不可）。*the present author* より I / we が自然。we は著者を指すときだけ使う。〔error〕
- **R4 包括的な we・you**：読者や人間一般を含む we（*We can see that …*、*As we know, …*、*We humans …*）は使わず、結果として述べる（*Figure 3 shows that …*、*The results indicate …*）。you も使わない。〔style。多い場合は clarity〕
- **R5 性別に中立な表現**：ガイドは単数の先行詞を they で受けず *he or she* とする立場。現在は APA 第7版などが単数の they を推奨しているので、規定に従う。指定がなければ複数形に書き換える（*participants … they*）のが最も無難。〔style〕

## F 図表（§5.1, §1.2）

- **F1 単独で理解できるか**：キャプションや表の注で、一般的な単位（cm、Hz、SD、N など）以外の略語をすべて定義する（本文で定義済みでも）。キャプション・表題は何を示すかを具体的に書く。〔未定義の略語は error、説明不足は clarity〕
- **F2 本文との一致**：図表の中の用語・略語・群の名前は本文と同じにする。図表・本文・要旨で重なる数値が一致しているか。**数値の食い違いは校正者が直さず query**。〔用語は error、数値は query〕
- **F3 番号と言及**：すべての図表が本文で番号付きで言及され、初出順に番号が振られている（Figure 1 より前に Figure 2 に言及しない）。番号の飛び・重複がない。〔error〕
- **F4 ラベルの書式**：本文での参照（*Fig. 1* / *Figure 1*、*Table 1*）とキャプションの書式を統一する（規定に従う）。番号の後の記号（*Table 1.* / *Table 1:*）を統一する。表題は表の上、図のキャプションは図の下が一般的。文頭の扱いは方式による：APA や多くの誌は文頭で略さず *Figure*、IEEE は文頭でも *Fig.*。規定が無ければ、引用方式から推定される方式と原稿の多数派に合わせ、style sheet に書く。〔error〕
- **F5 図表の中の語**：判読できるか、語が不自然に改行されていないか、大文字化が全図表で統一されているか、他言語（日本語の軸ラベルなど）が残っていないか。他者の著作物の図には出典を示す。テキスト抽出では図の中の語が読めないことがあるので、図表の多いページは画像で確認する。〔error / 出典は query〕

## C 引用・文献・直接引用・注（§5.2）

- **C1 引用の位置**：他者のアイデア・方法・結果・言葉を使ったら出典を示す。段落全体が同じ文献に依拠するなら、最初に使う文に出典を置く（段落末だけでは不十分）。文の一部だけが文献に基づくなら、その部分の直後に置く。直接引用には直ちに出典とページ番号。出典が抜けていそうな主張は query（校正者は出典を作らない）。文献リストにある文献の番号を、人名・手法名の言及に付ければよさそうな場合も、どの文献を指すかは著者が決めることなので query にし、案を示す。〔query / 位置の誤りは error〕
- **C2 本文中の引用の書式（著者年方式）**：同じ著者の複数の文献は年順（*Smith, 2010, 2014*）。異なる著者はセミコロンで区切り、規定の順に並べる（APA は著者名のアルファベット順）。著者名と年の間のコンマの有無、*&* と *and*（APA：カッコ内は &、本文中は and）、et al. を使い始める著者数（APA 第7版は3人以上で初出から。古い版や他の方式は異なる）、同じ著者・同じ年の a / b（*2020a, 2020b*。文献リストも）。〔error〕
- **C3 引用の書式（番号方式）**：Vancouver や IEEE は本文の初出順に番号を振り、同じ文献には同じ番号を使う。範囲（*[3–5]*）と列挙（*[1, 4]*）の書き方、カッコの種類（[1] / (1) / 上付き）を統一する。上付き番号と句読点の位置は P6。〔error〕
- **C4 本文の引用と文献リストの一致**：本文の著者名の綴り・年・番号が文献リストと一致するか。引用しているのにリストにない文献、リストにあるのに引用していない文献（References は引用したものだけ。Bibliography なら未引用も可）。明らかな綴りの揺れは error として揃え、どちらが正しいか分からなければ query。〔error / query〕
- **C5 文献リストの書式**：並び順（著者年方式はアルファベット順・同じ著者は年順、番号方式は番号順）、著者名の書き方（*Smith, J.* / *J. Smith*）、タイトルの大文字化（sentence case / title case）、イタリック・太字（誌名・巻）、句読点、ページ範囲の書式（222–224 / 222–24）、巻・号、DOI / URL。一部の文献だけ書式が違うのは文献管理ソフトの典型的な不具合（§5.3）。英語以外の文献のタイトルには英訳を [ ] で添えることがある。書誌情報の欠落（巻・ページ・年・出版社）は query。**タイトル自体の綴りは原典のまま**直さない。〔error / query〕
- **C6 直接引用**：直接引用には一種類の引用符を使い、強調や「いわゆる」には別の種類を使う。引用をイタリックで示さない。引用文は原文どおり（綴り・句読点も）。文頭の大文字を小文字にする程度の変更は可。語を補うときは [ ]、省くときは …。長い引用（目安40語以上）はブロック引用にして引用符を付けない。自分で加えた強調はその旨を書く。**校正者は引用文の中身を直さない**（原文と照合できないので、明らかな誤記は query）。〔error / query〕
- **C7 脚注・後注**：完全な文で書き、句読点も本文と同じ水準にする。番号の位置は P6。本文と同じフォント。規定が脚注を制限していれば従う。著者年方式・番号方式の論文で、脚注を出典表示だけに使わない。〔error / style〕

## K タイトル・要旨・キーワード（§6.2）

- **K1 タイトル**：簡潔か（APA は12語以内を推奨。規定の語数・文字数の制限）。*A Study of*、*Research on*、*An Investigation into*、*Results of* などの不要語を削る。略語を避ける。大文字化（Title Case / Sentence case）を規定どおりにする。タイトルと副題の区切り（コロン / ダッシュ）。研究対象・変数とその関係が分かるか。〔規定・文法は error、それ以外は style〕
- **K2 要旨**：論文の内容を要約するもので、評価や宣伝ではない。本文にない情報を含めない。語数の制限（多くは150〜250語）。背景・目的、対象、方法、主な結果、含意・結論を含むか（構造化要旨なら規定の見出しで）。引用は原則入れない。略語は最小限にし、要旨の中で定義する。最初の文の完成度が特に重要。1文あたりの情報量を高くし、機能語を減らす。受動態の多用（T3）。要旨と本文で数値や主張が食い違えば query。〔error / clarity / style〕
- **K3 キーワード**：数（多くは3〜8）、区切り（コンマ / セミコロン）、大文字化、並び順を規定どおりに。*and*、*or*、*between* などのつなぎ語を含めない。その語がタイトルや要旨にも使われているか（検索されやすさ）。〔error / style〕

## L 論理の明確さ（言葉の範囲で）（§1.2, §1.3）

校正の対象は言葉。主張そのものの妥当性は査読の範囲なので、ここでは書き方だけを扱う。

- **L1 主張の強さ**：証拠より強い語（*prove*、*clearly*、*obviously*、*always*、*never*、*perfectly*）は query。*prove* → *show* のような言い換えは主張の強さを変えるので、校正者が勝手に直さず著者に確認する。推測や一般化に限定の語（*may*、*suggest*、*in this dataset*）があるか。〔query / clarity〕
- **L2 結果の文**：結果を報告する文は、短く単純な構造の方が誤解がない（§1.2）。挿入句が多い長文（目安40語超）は分割する。指示語より名詞（W2）。〔clarity〕
- **L3 方法の説明**：誰が何をしたのか分からない受動態の連続など、読者が手順を追えない書き方。内容の不足は query。〔clarity / query〕

## E 英文法（補足：非ネイティブの英語論文に多い誤り）

- **E1 冠詞**：可算名詞の単数に冠詞がない（*We propose method* → *We propose a method*）。初出の不特定のものに the。総称の複数に the（*The previous studies have shown* → *Previous studies have shown*。特定の研究群を指すなら the でよい）。固有名詞・手法名・データセット名の扱い（*the Adam optimizer*、*ImageNet*）。略語の a / an は読み方で決める（*an SVM*、*a UNet*）。〔error〕
- **E2 主語と動詞の一致**：*The number of samples are* → *is*。*Each of the models have* → *has*。長い主語の後の動詞。集合名詞は文脈で。*data* は style sheet に従う。〔error〕
- **E3 可算・不可算と複数形**：information、research、evidence、equipment、software、feedback、knowledge、advice は不可算（*informations*、*researches* は誤り。*a research* → *a study*、*many researches* → *many studies*）。*less* と *fewer*。〔error〕
- **E4 前置詞**：*discuss / consider / mention / explain about* の about は不要。*different from*、*compared with / to*、*based on*（based of は誤り）、*consist of*、*depend on*、*focus on*、*in this paper*、*comprise*（*comprised of* は避ける）。〔error〕
- **E5 品詞・語形**：形容詞と副詞（*significant improved* → *significantly improved*）、名詞と動詞（*the analyze* → *the analysis*）、動名詞と to 不定詞（*aim to do*、*avoid doing*、*enable X to do*）、比較級の重複（*more faster*）。〔error〕
- **E6 文の構造**：主節のない文（*Because the model failed.*）、コンマで2文をつなぐ（comma splice：*The model converged quickly, this shows …*）、ぶら下がり修飾（*Using this method, the accuracy improved* → *Using this method, we improved the accuracy*）、並列構造の崩れ（*not only A but also B* の A と B の形）、対応する組のない *respectively*。〔error / clarity〕
- **E7 語順**：*only* の位置で意味が変わる。間接疑問の語順（*we examine how is the model affected* → *how the model is affected*）。形容詞の順。〔error〕
- **E8 誤字・脱字**：単純な綴りの誤り、語の重複（*the the*）、抜けた語。〔error〕
- **E9 直訳調**：*It can be considered that* → *This suggests that* / *We consider that*、*In recent years,* や *In this paper,* の多用、*As mentioned above,* の多用、*and so on*、*etc.* の多用、*make clear* → *clarify*、*carry out* の多用 → *perform / conduct*、冗長な *it is necessary to*。直訳で意味が通らない文は query にし、意図を推測した案を添える。〔style / clarity〕

## X 指摘しないもの（抽出・組版の副作用）

- 行末のハイフン：PDF の行末で語が分かれているのは組版の自動ハイフネーション。指摘しない。複合語のハイフンかどうかは次の行とつなげて判断する。
- 合字（ﬁ、ﬂ）、特殊な空白、2段組の抽出順の乱れ、数式のテキストの崩れは抽出の副作用。指摘しない。数式そのものは校正しない（数式の前後の英文は対象）。
- ヘッダー・フッター・ページ番号・行番号・著作権表示・arXiv のスタンプは対象外。
- ただし LaTeX の `??` や `[?]`（未定義の参照）は本物の誤り（G3）。
