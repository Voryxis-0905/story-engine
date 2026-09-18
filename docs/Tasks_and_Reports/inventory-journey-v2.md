# Inventory & Journey v2

## Hành vi

- Item instance có `instance_id`; hai vật phẩm cùng tên không tự nhập làm một.
- Chỉ item có `stackable=true`, cùng `item_id` và cùng trạng thái mutable mới cộng quantity.
- Các lệnh Inspect/Use/Equip/Unequip/Drop được engine kiểm tra quyền sở hữu. UI chỉ chuẩn bị câu lệnh để player sửa trước khi gửi.
- `POST /worlds/{world}/travel/preview` chỉ đọc state, không roll encounter và không gọi LLM.
- Travel encounter lưu `active_journey` trong `world_config.json`. Player có thể tiếp tục phần đường còn lại hoặc bỏ hành trình.
- `discovery_status` của location gồm `unknown`, `rumored`, `discovered`, `visited`, `creator_only`. Player không nhận tên/mô tả/tag của node ẩn.
- Creator edit hỗ trợ item instance, route/location visibility và active journey qua cùng revision log hiện có.

## Dữ liệu và tương thích

Schema world tăng lên v6. Migration v5→v6 thêm `active_journey: null`; inventory string và map edge dạng string cũ tiếp tục đọc được. Vì journey nằm trong core `world_config.json`, save/restore/branch/export và pre-turn snapshot tự mang trạng thái này.

World cũ không có `discovery_status` mặc định là `discovered`. Quy tắc này tránh làm mất map sau nâng cấp.

## Giới hạn

- `Use` chỉ tự giảm `charges` khi field này là số; item có tag `consumable` và stackable giảm một quantity. Hiệu ứng truyện khác vẫn đi qua action/state pipeline.
- Fog of war hiện do dữ liệu location quyết định; chưa có editor đồ họa riêng để author kéo thả route.
- Chất lượng văn kể hành trình chưa được đánh giá bằng model trả phí.
