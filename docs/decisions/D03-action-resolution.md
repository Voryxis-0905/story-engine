# D03 — Giải quyết hành động đa thể loại

Trạng thái: **ĐÃ DUYỆT 18/09/2026** theo các mặc định đề xuất (chủ dự án chốt). W04 có thể triển khai. Phần biến đổi tính cách có thể hoãn; profile nhân vật vẫn dùng ngay.

Căn cứ: [DESIGN-PRINCIPLES.md](../DESIGN-PRINCIPLES.md), [../AGENT-BACKLOG.md](../AGENT-BACKLOG.md) mục D03.

## 1. Không một thang sức mạnh cho mọi thể loại

Trinh thám, đời thường và fantasy không dùng chung "level". Bộ giải quyết phải đọc bối
cảnh và nguồn lực cụ thể của từng hành động. Fantasy có thể có realm/EXP; đời thường
không cần, và không được coi realm/EXP là bắt buộc để hành động.

## 2. Các thành phần đánh giá

| Thành phần | Câu hỏi | Nguồn dữ liệu |
| --- | --- | --- |
| Năng lực | Nhân vật có kỹ năng/phẩm chất cần thiết? | `power_stat`, `known_skills`, traits, tiểu sử |
| Công cụ | Có vật phẩm/điều kiện cần? | `inventory`, card item |
| Tiếp cận | Có tới được đối tượng/vị trí? | bản đồ, boundary, vị trí |
| Môi trường | Thời gian, thời tiết, địa hình, người xung quanh | `story_clock`, location tags, perception |
| Đối kháng | Ai/cái gì chống lại, mạnh yếu ra sao? | NPC state, affinity, kế hoạch |
| Đánh đổi | Làm được thì mất gì (thời gian, quan hệ, cơ hội)? | hệ quả thiết kế, event |

## 3. Quyết định xác định hay xác suất

Đề xuất: **lai**.
- Kiểm tra **bất khả thi/có điều kiện** là xác định (rule-based): thiếu công cụ thì không
  thể mở khoá; thiếu tiếp cận thì không tới nơi.
- Khi hành động *có thể* nhưng kết quả không chắc (đối kháng, may mắn), dùng xác suất **có
  seed/log tái hiện được**.
- **Không** gọi xác suất do LLM tự bịa là số đo khách quan. Nếu LLM chỉ kể lại kết quả đã
  chốt, đó là tự sự, không phải cơ chế.

## 4. Bốn mức kết quả

| Mức | Khi nào | Điều xảy ra tiếp |
| --- | --- | --- |
| `impossible` | Thiếu hẳn nguồn lực/điều kiện | Giải thích luật thế giới; mở hướng khác, không bế tắc |
| `conditional` | Có thể nếu chấp nhận điều kiện/đánh đổi | Người chơi chọn tiếp; điều kiện được ghi vào state |
| `partial` | Thành công một phần hoặc có giá | Đạt mục tiêu kèm mất mát/hệ quả |
| `success` / `failure` | Kết quả rõ | Có diễn biến tiếp cho cả hai; thất bại không kết thúc hành trình |

Mỗi kết quả có **trường dữ liệu thống nhất** để writer không tự đổi kết quả đã commit:

```json
{
  "action_id": "act_0007",
  "intent": "mở khoá cửa sập bằng chìa",
  "checks": [
    {"name": "tool", "ok": false, "detail": "không có chìa"},
    {"name": "access", "ok": true}
  ],
  "result": "conditional",
  "reason": "thiếu chìa, nhưng có thể cạy bằng đoản kiếm (ồn, gây chú ý)",
  "consequences": [{"type": "noise", "value": "high"}],
  "seed": 18342
}
```

## 5. Cùng kiểu hành động ở ba thể loại

Hành động minh hoạ: *"thuyết phục/dọa người trước mặt nói ra sự thật"*.

- **Trinh thám**: đánh giá bằng chứng đã thu thập + tâm lý đối tượng + thời gian còn lại.
  Kết quả `conditional`: nói ra nhưng chỉ nếu sắp xếp buổi đối chất. Không cần level.
- **Đời thường**: đánh giá quan hệ, uy tín, lời hứa trước đó. Kết quả `partial`: nói nửa
  sự thật, cái còn lại để sau. Không có EXP.
- **Fantasy**: có thể có áp chế tu vi, nhưng vẫn phải kiểm tra công cụ/pháp bảo. Kết quả
  `failure`: đối phương có bùa hộ mệnh, mở hướng điều tra khác.

Cả ba đều dùng cùng bảng `checks` + `result` + `reason`; chỉ nội dung check khác nhau.

## 6. Biến đổi tính cách

Đề xuất: cho phép thay đổi **có giới hạn và có nguyên nhân** (sự kiện lớn, chuỗi trải
nghiệm), có log. Việc này có thể hoãn sau W04; profile tĩnh vẫn dùng được ngay. Không đổi
tính cách tuỳ tiện chỉ để hợp thức hoá một hành động.

## 7. Câu hỏi chờ chốt

1. Seed lấy từ đâu để "tái hiện"? Đề xuất: seed theo `(world, branch, turn, action_id)`.
2. Có cho phép `conditional` khiến player phải chọn lại ngay trong cùng lượt không, hay
   để lượt sau? Đề xuất: cùng lượt nếu điều kiện đơn giản, lượt sau nếu cần cảnh mới.
