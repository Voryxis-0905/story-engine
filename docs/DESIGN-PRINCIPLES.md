# Nguyên tắc thiết kế — trao đổi ngày 17/09/2026

Tài liệu này phân biệt điều chủ dự án đã xác định với đề xuất còn cần chốt. Đây là định hướng, không khẳng định code hiện đã thực hiện đầy đủ.

## Đã xác định

1. Player điều khiển hành động và tác động đến kết quả. Creator cũng là player, nhưng có quyền trực tiếp thay đổi kết quả.
2. Hướng checkpoint mong muốn: sự việc xảy ra, còn kết quả mở theo tác động của player và diễn biến thế giới. Không cố định một kết quả duy nhất.
3. Thế giới lưu sự thật về ai/cái gì tồn tại và những gì đang diễn ra. Nhân vật có góc nhìn hạn tri riêng.
4. Profile, tính cách và sự kiện trong đời nhân vật ảnh hưởng đến suy nghĩ và hành vi. Không cho NPC tự biết thông tin chỉ vì engine biết.
5. Player có góc nhìn rộng hơn qua quest, túi đồ, bản đồ. Quest có thể là nơi thông báo sự kiện/cơ hội.
6. Engine hỗ trợ nhiều thể loại; cảnh giới và thứ bậc không phải giả định bắt buộc.
7. Nhật ký thế giới ghi diễn biến và làm kênh giao tiếp với player. Quan hệ phải có ký ức cụ thể.
8. Thất bại vẫn mở diễn biến tiếp theo. Tự do và kết quả mở là yêu cầu nền tảng.
9. World builder có bước xem/sửa; tiến độ và chi phí có một menu nhỏ riêng.
10. Bộ tình huống đánh giá cố định dữ kiện để kiểm tra luật; không cố định kết quả truyện của player.

## Đề xuất đang cần chốt

- Checkpoint mất điều kiện vì hành động trước đó: chuyển hình thức hay có thể bị hủy? Phân biệt biến cố bất khả kháng với sự kiện do nhân vật tổ chức.
- Player được xem thông tin vượt góc nhìn nhân vật đến mức nào? Quy tắc tránh spoil trên quest/map/log.
- Đánh giá hành động theo năng lực, công cụ, quyền tiếp cận, môi trường, đối kháng, đánh đổi và bất định; xác định luật nhất quán cho từng world.
- Mức biến đổi tính cách theo trải nghiệm, thay vì profile bất biến.
- Cách ghi nhận sửa đổi của Creator và ảnh hưởng đến lịch sử/nhánh truyện.

Không chuyển những đề xuất này thành luật cứng mà chưa đối chiếu với ý định chủ dự án.
