# Dashboard báo cáo Facebook Ads (bản làm lại theo mẫu thammyha)

App Streamlit đọc số liệu Facebook Ads theo tài khoản + khoảng thời gian, gồm các tab:
- **Tổng quan**: Tổng chi tiêu, Tin nhắn, Chi phí/tin nhắn, CTR, SĐT, Giá SĐT, tổng hợp theo tài khoản.
- **Chiến dịch**: bảng chiến dịch (chi tiêu, tin nhắn, giá/tin, SĐT, NS/ngày) + Tải CSV.
- **Cảnh báo**: chiến dịch "tiêu tiền nhưng 0 tin nhắn", giá tin nhắn quá cao, TKQC có thể bị vô hiệu hóa.
- **Thêm**: ngưỡng cảnh báo + rule tăng/giảm ngân sách (chỉ đề xuất, không tự đổi).

## 1. Chạy thử trên máy
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # rồi điền token thật
streamlit run app.py
```

## 2. Lấy Access Token Facebook
1. Vào **developers.facebook.com** → tạo App (loại Business).
2. Thêm sản phẩm **Marketing API**.
3. Cấp quyền: `ads_read`, `business_management`, `leads_retrieval` (nếu cần lấy SĐT từ form).
4. Dùng **Graph API Explorer** lấy token, sau đó đổi sang **token dài hạn** (long-lived) hoặc token System User trong Business Manager (bền nhất, không hết hạn).
5. Lấy **Ad Account ID** (dạng `act_123...`) trong Ads Manager → Cài đặt tài khoản.

Điền vào `.streamlit/secrets.toml`:
```toml
api_version = "v21.0"
access_token = "EAA...token..."

[accounts]
"01 TRUNG HM VK" = "act_1234567890"
"02 TRUNG HM VN" = "act_9876543210"
```

## 3. Deploy lên streamlit.app (như bản gốc)
1. Đưa thư mục này lên **GitHub** (KHÔNG commit file `secrets.toml` thật — đã có trong gợi ý bỏ qua).
2. Vào **share.streamlit.io** → New app → chọn repo → file `app.py`.
3. Vào **Settings → Secrets** của app, dán nội dung `secrets.toml` (token + accounts).
4. Deploy. App sẽ có link `https://<ten>.streamlit.app` giống bản gốc.

## 4. Chỉnh cho đúng số của bạn
- Nếu **Tin nhắn** hoặc **SĐT** hiển thị sai (0 hoặc lệch), vào tab **Thêm → Loại action** sửa `action_type`:
  - Tin nhắn thường là `onsite_conversion.messaging_conversation_started_7d`.
  - Lead form có thể là `lead`, `leadgen_grouped`, `onsite_conversion.lead_grouped`...
  - Mở Graph API Explorer gọi `act_xxx/insights?fields=actions` để xem đúng tên action tài khoản bạn đang trả về.

## Giới hạn (nói thẳng)
- App **chỉ đọc** (ads_read). Không tự tăng/giảm ngân sách — rule chỉ hiện đề xuất để bạn tự chỉnh trên Ads Manager, giống bản gốc.
- "SĐT từ form" chỉ đúng nếu bạn chạy **Lead Form** của Facebook; nếu lấy SĐT qua inbox/chatbot thì con số này sẽ khác (chỉnh action_type hoặc bỏ qua).
- Token hết hạn thì app báo lỗi — dùng token System User để khỏi phải thay.
