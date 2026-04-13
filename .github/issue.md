# 問題清單與處理狀態

**最後更新**：2026-04-13

## ✅ 已完成項目

### 1. 系統音錄音失效
- **狀態**：✅ 已修正
- **問題**：使用 `sc.default_speaker()` 無法取得 loopback 裝置
- **解決**：改用 `sc.all_microphones(include_loopback=True)` + `isloopback` 屬性篩選
- **檔案**：`src/recorder.py`

### 2. 即時轉錄中文變英文
- **狀態**：✅ 已修正
- **問題**：即時轉錄時未傳遞 `language` 和 `initial_prompt` 參數
- **解決**：所有轉錄方法統一接收並傳遞語言設定
- **檔案**：`src/stt.py`, `main.py`

### 3. 按鈕狀態邏輯
- **狀態**：✅ 已修正
- **問題**：即時/非即時模式下「停止錄音並轉錄」按鈕狀態錯誤
- **解決**：
  - 即時模式：按鈕鎖定 (DISABLED)
  - 非即時模式：按鈕啟用 (NORMAL)
- **檔案**：`main.py` (`start_record_thread`, `_on_realtime_change`, `_restore_record_btn`)

### 4. 選檔案轉錄流程
- **狀態**：✅ 已修正
- **問題**：選檔案時未根據即時/非即時模式選擇轉錄方式
- **解決**：
  - 即時模式：`transcribe_file_stream` (分段串流)
  - 非即時模式：`transcribe_file_batch` (整檔批次)
- **檔案**：`main.py` (`transcribe_selected_file`)

### 5. 完成訊息缺失
- **狀態**：✅ 已修正
- **問題**：無法判斷 STT 是否完成
- **解決**：所有流程結束時顯示「✓ 已完成」
- **檔案**：`main.py` (所有轉錄方法)

### 6. 系統訊息不足
- **狀態**：✅ 已修正
- **問題**：無法追蹤執行狀態
- **解決**：每個動作都記錄系統訊息
- **涵蓋**：開始錄音、停止錄音、選檔案、轉錄模式、完成狀態

### 7. 程式主流程文件
- **狀態**：✅ 已完成
- **檔案**：`project.md` 新增流程圖與各模式說明

### 8. 即時轉錄 chunk 太短問題
- **狀態**：✅ 已修正 (2026-04-13)
- **問題**：即時轉錄每 0.2 秒 chunk 立即轉錄，導致 Whisper 輸出 prompt 片段而非實際內容
- **解決**：累積音訊到 2.5 秒再進行轉錄
- **效果**：
  - 提高轉錄準確度
  - 減少 Whisper 調用次數
  - 延遲增加到 2.5 秒（仍屬即時範圍）
- **檔案**：`main.py` (`transcription_worker`)

### 9. 選檔+即時轉錄 未輸出文字檔
- **狀態**：✅ 已修正 (2026-04-13)
- **問題**：選擇音檔並勾選「即時轉錄」完成後，只在介面顯示文字，未輸出 txt 檔案
- **原因**：`transcribe_file_stream` 方法缺少文字檔保存邏輯
- **解決**：在轉錄完成後從 `result_area` 讀取文字並呼叫 `save_note` 保存
- **效果**：四種轉錄模式（錄音+即時、錄音+批次、選檔+即時、選檔+批次）現在都會輸出文字檔
- **檔案**：`main.py` (`transcribe_file_stream`)

### 10. STT 輸出 prompt 內容問題
- **狀態**：✅ 已修正 (2026-04-13)
- **問題**：STT 結果中出現 initial_prompt 內容（如「以繁體中文為主」）
- **原因**：當音訊段沒有語音或質量差時，Whisper 會輸出 prompt 文字
- **解決**：在 `transcribe_chunk` 中加入過濾機制，比對結果與 prompt（移除標點後），相同則忽略該段
- **效果**：避免 prompt 汙染轉錄結果
- **檔案**：`src/stt.py` (`transcribe_chunk`)

### 11. 系統自動判斷誤判語言問題
- **狀態**：✅ 已修正 (2026-04-13)
- **問題**：
  - 選擇「系統自動判斷」時，中文音訊被誤判為英文
  - 輸出英文亂碼和 prompt 片段 "This is a discussion in English and Traditional Chinese"
- **原因**：
  - 原 prompt 是英文（"This is a discussion in English and Traditional Chinese (Taiwan)."），引導 Whisper 傾向英文
  - Prompt 變體（缺少 "Taiwan"）沒被過濾機制捕捉
- **解決**：
  1. 修改「系統自動判斷」的 prompt 為中文：「繁體中文與英文混合討論。」
  2. 改善過濾邏輯：計算 prompt 佔結果的比例，若 >80% 則過濾
- **效果**：避免英文 prompt 引導語言誤判
- **檔案**：`main.py` (`get_initial_prompt`), `src/stt.py` (`transcribe_chunk`)
- **後續強化**：增加反向檢查（結果是否為 prompt 子字串）+ 特徵詞過濾（「混合討論」等）

### 12. 新增清除按鈕
- **狀態**：✅ 已完成 (2026-04-13)
- **功能**：在按鈕列最右邊新增「清除」按鈕，用於清空轉錄結果視窗
- **效果**：方便使用者重新開始新的轉錄任務
- **檔案**：`src/ui.py` (按鈕), `main.py` (`clear_result_area`)

### 13. UI 布局優化
- **狀態**：✅ 已完成 (2026-04-13)
- **調整**：將「錄音來源」選單移到「語言模式」右邊，整合為單行控制列
- **效果**：更緊湊的介面，節省垂直空間
- **檔案**：`src/ui.py`

### 14. 打包配置更新
- **狀態**：✅ 已完成 (2026-04-13)
- **更新**：
  - 優化排除模組清單（matplotlib, IPython, jupyter, pytest）
  - 自訂 exe 名稱為 `AI_STT_Transcriber.exe`
  - 改善打包流程訊息顯示
  - 更新 project.md 打包部署章節，提供完整檢查清單
- **效果**：減少 exe 體積，提升打包效率
- **檔案**：`build_exe.py`, `project.md`

### 15. 動態模型清單
- **狀態**：✅ 已完成 (2026-04-13)
- **功能**：程式啟動時自動掃描 model/ 資料夾，根據實際存在的模型動態產生清單
- **掃描邏輯**：
  - Faster-Whisper：檢查 `model/faster-whisper/*/config.json`
  - OpenAI Whisper：檢查 `model/whisper/*.pt`
  - 未找到模型時使用預設清單（避免程式無法啟動）
- **效果**：支援彈性打包，不同環境可提供不同模型組合
- **檔案**：`main.py` (`scan_available_models`), `src/ui.py`

## 📋 待確認項目

### 音量顯示器
- **狀態**：⚠️ 需測試
- **檢查**：
  - 程式碼邏輯正確 ✓
  - `recorder.py` 正確計算 RMS 並調用 `on_volume` ✓
  - `ui.py` 正確繪製音量條 ✓
- **待確認**：實際錄音時音量條是否正常跳動

## 🔧 技術備註

### 語言設定方案
```python
# UI 選項 → Whisper 參數
"主要中文" → language='zh', prompt="以繁體中文為主，夾雜英文術語。"
"主要英文" → language='en', prompt="This is a technical meeting in English."
"系統自動判斷" → language=None, prompt="繁體中文與英文混合討論。"
```

### 轉錄流程分類
| 模式 | 方法 | 特性 | 輸出文字檔 |
|------|------|------|-----------|
| 錄音+即時 | `transcription_worker` → `transcribe_chunk` | 累積 2.5 秒後轉錄，即時顯示 | ✅ 停止時輸出 |
| 錄音+非即時 | `record_logic` → `transcribe_file_batch` | 錄完後整檔轉錄 | ✅ 完成時輸出 |
| 選檔+即時 | `transcribe_file_stream` | 分段串流，進度更新 | ✅ 完成時輸出 |
| 選檔+非即時 | `transcribe_file_batch` | 整檔批次，一次顯示 | ✅ 完成時輸出 |

### 即時轉錄 Buffer 機制
```
Recorder (0.2s chunk) → Queue → Buffer (累積到 2.5s) → Whisper → UI
                           ↓
                    音量顯示 (即時)
```

- **Recorder chunk**：0.2 秒（用於音量顯示，保持即時性）
- **STT buffer**：累積到 2.5 秒再轉錄（確保 Whisper 有足夠音訊）
- **延遲**：約 2.5 秒（可接受的即時範圍）

### 按鈕狀態規則
```
即時轉錄勾選時：
  - 錄音中：「停止錄音並轉錄」DISABLED
  - 未錄音：「停止錄音並轉錄」DISABLED

即時轉錄未勾選時：
  - 錄音中：「停止錄音並轉錄」ENABLED
  - 未錄音：「停止錄音並轉錄」NORMAL (可按)
```

## 📝 開發注意事項

1. **模組化原則**：
   - `main.py` 只做流程編排
   - 業務邏輯放 `src/` 模組

2. **UI 分區**：
   - 「轉錄結果」區：只顯示 STT 文字
   - 「系統訊息」區：狀態、錯誤、日誌

3. **語言參數**：
   - 所有轉錄方法必須接收 `language` 和 `initial_prompt`
   - 使用 `_get_language_code()` 統一轉換

4. **完成訊息**：
   - 正常結束：「✓ 已完成」
   - 使用者中止：「已停止」
   - 發生錯誤：「失敗：{原因}」

5. **Prompt 過濾機制**（重要）：
   - Whisper 在處理無語音/低質量音訊時會輸出 prompt 內容
   - `transcribe_chunk` 會自動過濾與 prompt 相同的結果（移除標點後比對）
   - **多重過濾策略**：
     1. 完全相同檢查
     2. Prompt 佔比 >80% 過濾
     3. 反向檢查：結果是否為 prompt 子字串（處理變體，如「中文與英文混合討論」vs「繁體中文與英文混合討論」）
     4. 特徵詞過濾：短結果包含「混合討論」、「technical meeting」等 prompt 標誌詞
   - 確保 prompt 不汙染實際轉錄內容

              on_volume=push_volume_to_queue
           )
      -> Thread2(STT):
           while not stop_transcribe_flag:
               chunk = audio_queue.get()
               text = transcriber.transcribe_chunk(chunk)
               ui_queue.put(("text", text))

      -> 主執行緒(root.after輪詢):
           - 取 ui_queue 的 text -> append_stt_text
           - 取 volume_queue -> update_volume
           - 需要時更新系統訊息

    [按:停止轉錄]  (或你也可把它當成 "停止即時模式")
      -> 設 stop flags
      -> 等 thread 結束
      -> 系統訊息: "已完成"
      -> 回到 IDLE，解鎖按鈕

***

### B. 錄音 + ❌未勾選即時轉錄（realtime=False）

    [按:開始錄音]
      -> 系統訊息: "開始錄音"
      -> 狀態: RECORDING
      -> 按鈕:
           - 開始錄音 disabled
           - 停止錄音並轉錄(btn_stop) enabled (符合需求#4)

    [按:停止錄音並轉錄]
      -> 系統訊息: "停止錄音，開始轉錄"
      -> 停止錄音 thread，取得 wav_path
      -> 狀態: TRANSCRIBING
      -> Thread(STT檔案):
           transcriber.transcribe_file_stream(
              wav_path,
              on_segment=push_text_to_ui_queue,
              progress_callback=push_progress_to_ui_queue,
              stop_callback=stop_transcribe_flag
           )
      -> 主執行緒(root.after):
           append_stt_text / 更新進度
      -> 完成:
           系統訊息: "已完成"
           回到 IDLE，解鎖按鈕

***

### C. 選取檔案 + ✅勾選即時轉錄（realtime=True）

    [按:選取檔案]
      -> 系統訊息: "選取檔案..."
      -> (建議) 先 utils.prepare_for_stt 轉 16k mono wav
      -> 系統訊息: "開始處理音檔，即時轉錄"
      -> 狀態: TRANSCRIBING
      -> Thread:
           transcriber.transcribe_file_stream(
              prepared_wav,
              on_segment=push_text,
              progress_callback=push_progress,
              stop_callback=stop_transcribe_flag
           )
      -> 主執行緒(root.after):
           append_stt_text / 更新進度
      -> 完成:
           系統訊息: "已完成"
           回到 IDLE

***

### D. 選取檔案 + ❌未勾選即時轉錄（realtime=False）

> 你的需求 #6：「先處理音檔，之後再執行 STT」要成立，需要流程切兩段。

    [按:選取檔案]
      -> 系統訊息: "選取檔案..."
      -> 先 utils.prepare_for_stt()
      -> 系統訊息: "音檔處理完成，等待開始轉錄"

    (下一步觸發點需要你定義)
      方案1：新增一個 [開始轉錄] 按鈕
      方案2：沿用某個按鈕當作 "開始轉錄"
      方案3：你接受「處理完就自動開始轉錄」（那就不算"之後再"）

    [開始轉錄]
      -> Thread: transcribe_file_to_text 或 transcribe_file_stream
      -> 完成: 系統訊息 "已完成"

***

# 針對你 3\~6 點：按鈕鎖定/行為規格（你要的就是狀態機）

你列的 #3\~#6 本質上要做「狀態機 + UI enable/disable」。

## 3) 勾選即時轉錄時，「停止錄音並轉錄」要一直鎖住不能按

*   在 `realtime=True` 且「正在錄音」的狀態下：
    *   `btn_stop` 永遠 disabled
    *   讓使用者用 `btn_stop_trans` 來停止即時流程（或你改成「停止錄音」）

## 4) 沒勾選即時轉錄時，「停止錄音並轉錄」可以按

*   `realtime=False` 且「正在錄音」時：
    *   `btn_stop` enabled
    *   點下去：停止錄音 → 開始 STT

## 5) 選檔 + 勾即時：立刻開始處理音檔並即時 STT

*   選檔後直接跑 `transcribe_file_stream`（邊讀邊轉）

## 6) 選檔 + 未勾即時：先處理音檔，之後再執行 STT

*   你必須提供「第二步觸發」：
    *   最乾淨：新增 `btn_start_transcribe`（開始轉錄）
    *   或你接受「處理完就自動轉錄」（那就少一段）

***

# 7) 完成時必須顯示「已完成」

這條你說得非常對：沒有「已完成」，使用者無法判斷狀態。

**規格建議：所有流程（錄音/選檔、即時/非即時）只要正常結束，都要寫入：**

*   系統訊息：`已完成`

另外也建議補上：

*   使用者中止：`已停止`
*   發生例外：`失敗：{錯誤原因}`

***

# 8) 左下方音量顯示器是否正常運作？

目前「元件設計」是對的，但「串接方式」不完整，因此大概率不會正常顯示。

## 你現在應該做到的正確方式（重點）

*   錄音是在背景 thread 跑
*   Tkinter UI 必須在主執行緒更新

### 正確作法

*   `record_single_source` 的 `on_volume(mic_pct, sys_pct)` **不要直接呼叫 update\_volume**
*   改成把音量值丟進 queue
*   主執行緒用 `root.after(50, poll_queue)` 把 queue 的值取出後再呼叫 `update_volume`

如果你目前是「背景 thread 直接畫 Canvas」，就會出現：

*   不更新 / 間歇更新
*   UI 卡頓
*   不穩定錯誤

***

# 9) 每種動作執行時，都應該顯示系統訊息

你要的是「可追蹤的狀態日誌」。建議每個事件都固定寫一行：

## 建議訊息清單（可直接照抄）

*   開始錄音：`開始錄音`
*   停止錄音：`停止錄音`
*   停止錄音並轉錄：`停止錄音，開始轉錄`
*   選取檔案：`選取檔案：{檔名}`
*   音檔預處理開始：`音檔處理中...`
*   音檔預處理完成：`音檔處理完成`
*   STT 開始：`開始轉錄`
*   STT 進度：`轉錄進度：{percent}%`（可選）
*   使用者中止：`已停止`
*   完成：`已完成`
*   錯誤：`失敗：{錯誤摘要}`

***

# 目前程式碼的「最關鍵問題清單」（直接點出你卡住的原因）

1.  **TranscriberApp 幾乎是空的**

*   沒建 UI
*   沒事件方法（start\_record\_thread / stop\_record / select\_file / stop\_transcription\_now / \_on\_realtime\_change / \_on\_model\_change / on\_closing）
*   沒 queue / thread / stop flags / 狀態機

2.  **UI 雖然畫好了，但按鈕綁定到不存在的方法**

*   所以你要求的 #3\~#9 都無法落地

3.  **缺少 thread-safe UI 更新**

*   音量顯示、即時文字 append、系統訊息輸出都需要 queue + root.after

4.  **選檔 + 非即時**流程缺一個「開始轉錄」的觸發點

*   你要「先處理再轉錄」就必須有第二步

5.  **檔案串流的暫存 wav 若用相對路徑，可能寫到不預期的位置**

*   建議改為絕對路徑（例如固定放 recordings/）

***


