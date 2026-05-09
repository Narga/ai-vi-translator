# Tách Backend Dùng Chung Cho CLI và WebUI

Ngày: 2026-05-09

## Mục tiêu

Tách phần xử lý nghiệp vụ ra khỏi `cli.py`, `main.py`, `webui/routes/*.py`, `webui/helpers.py` để:

- CLI và WebUI dùng chung một backend duy nhất.
- Mỗi tính năng hoặc bugfix chỉ sửa một lần ở backend.
- Chỉ giữ lại phần đặc thù giao diện ở CLI hoặc WebUI.
- Dự án luôn chạy bình thường trong suốt quá trình refactor.
- Mỗi giai đoạn đủ nhỏ để một model nhẹ vẫn có thể thực hiện tuần tự, ít rủi ro.

## Cơ sở đánh giá

Đánh giá này dựa trên GitNexus index đã refresh tại commit `da795bc`.

### Symbol và blast radius chính

- `core/executor.py:TranslationExecutor`
  - Risk: `MEDIUM`
  - Direct callers/dependents:
    - `main.py:main`
    - `webui/routes/translation.py:translate_worker`
    - `webui/routes/projects.py:_project_translate_worker`

- `cli.py:NovelTranslatorCLI`
  - Risk: `LOW`
  - Direct dependent:
    - `cli.py:main`

- `webui/__init__.py:create_app`
  - Risk: `LOW`
  - Direct dependent:
    - `webui.py`

## Hiện trạng mã nguồn

### Điểm tốt

- Đã có lõi dùng chung sơ bộ qua `TranslationExecutor` và `SpellcheckExecutor`.
- WebUI đã chia thành Blueprints.
- `services/` đã có nhiều primitive dùng lại được:
  - `config_service.py`
  - `checkpoint_service.py`
  - `cache_service.py`
  - `glossary_service.py`
  - `translation_memory.py`
  - `ai_provider.py`
  - `api_service.py`

### Điểm yếu chính

- `cli.py` gọi `main.py` bằng cách sửa `sys.argv`.
- `main.py` vừa là entrypoint, vừa chứa orchestration nghiệp vụ.
- `core/executor.py` còn dependency ngược sang `webui.helpers.calculate_stats`.
- `main.py` import `webui.helpers.ensure_default_project`.
- `webui/helpers.py` đang ôm quá nhiều trách nhiệm.
- `webui/routes/projects.py` rất lớn và chứa cả transport lẫn business logic.
- `webui/static/js/main.js` là frontend monolith lớn.

## Đánh giá logic vận hành hiện tại

### Luồng chạy thực tế của dự án

- CLI hiện có hai lớp entrypoint chồng nhau:
  - `cli.py` là parser và command dispatcher bề mặt
  - `main.py` là nơi chạy translation flow thật sự
- WebUI có một lớp app factory mỏng ở:
  - `webui.py`
  - `webui/__init__.py:create_app`
- Phần orchestration nghiệp vụ thật sự hiện nằm rải ở:
  - `main.py`
  - `webui/routes/translation.py`
  - `webui/routes/projects.py`
- Translation core hiện xoay quanh:
  - `core/executor.py:TranslationExecutor`
  - `services/api_service.py`
  - `services/cache_service.py`
  - `services/checkpoint_service.py`
  - `services/glossary_service.py`
  - `services/translation_memory.py`
- Spellcheck core hiện đi qua:
  - `core/spellcheck_executor.py:SpellcheckExecutor`

### Nhận định vận hành

- Dự án hiện là một `modular monolith` chưa hoàn tất ranh giới tầng.
- Phần chạy thực tế vẫn ổn vì translation engine đã gom phần khó nhất vào executor.
- Rủi ro lớn nhất không nằm ở thuật toán dịch, mà nằm ở orchestration bị nhân bản ở nhiều adapter.
- Nếu sửa trực tiếp vào route hoặc CLI mà không gom về backend dùng chung, xác suất lệch behavior giữa CLI và WebUI sẽ tiếp tục tăng.

### Lời khuyên kỹ thuật

1. Không thay translation algorithm trước.
2. Ưu tiên gom orchestration, config assembly, prompt resolution, workspace/project resolution về backend.
3. Giữ adapter cũ hoạt động bằng wrapper mỏng trong nhiều phase trung gian.
4. Mỗi thay đổi phải ưu tiên tận dụng code đang chạy ổn trong `core/` và `services/`.
5. Chỉ tách frontend sâu sau khi backend contract ổn định.

## Kết luận kiến trúc

Không nên tách repo ngay.

Hướng phù hợp:

1. Giữ monorepo.
2. Tách backend dùng chung thành một lõi ứng dụng độc lập.
3. Biến CLI và Flask WebUI thành hai adapter mỏng.
4. Sau khi backend contract ổn định, mới cân nhắc tách frontend WebUI sâu hơn.

## Kiến trúc đích

```text
CLI Adapter            Flask API Adapter             Web Frontend
   |                         |                            |
   +----------- gọi chung Application Use Cases ---------+
                             |
                       Backend Core
                             |
        ---------------------------------------------------
        |                 |               |               |
     Domain           Services       Repositories      Gateways
                             |
                      File system / config / AI providers
```

## Quy tắc thực hiện bắt buộc

- Mỗi giai đoạn phải giữ nguyên hành vi public hiện có trừ khi tài liệu phase đó nói rõ.
- Không đổi nhiều điểm cùng lúc nếu chưa có baseline test hoặc smoke check.
- Mọi thay đổi vào symbol nghiệp vụ lớn phải chạy GitNexus impact trước khi sửa.
- Mỗi phase chỉ xử lý một nhóm trách nhiệm rõ ràng.
- Nếu phase chưa đạt tiêu chí hoàn tất thì không chuyển phase tiếp theo.

## Nguyên tắc sinh mã và sửa mã bắt buộc

Các nguyên tắc dưới đây áp dụng cho toàn bộ 15 phase. Mọi file kế hoạch con đều mặc định kế thừa, kể cả khi không lặp lại đầy đủ.

- Tham khảo cấu trúc dự án đã được GitNexus lập chỉ mục trước khi sinh mã mới.
- Ưu tiên tận dụng tối đa mã sẵn có trong:
  - `core/`
  - `services/`
  - `webui/helpers.py`
  - `webui/routes/*.py`
  - `main.py`
  - `cli.py`
- Chỉ viết mới khi:
  - đã xác nhận trong kế hoạch phase hiện tại
  - hoặc thực sự không có mã sẵn phù hợp để tái sử dụng
- Không sinh mã inline ở giao diện nếu dự án đã có template hoặc cấu trúc sẵn.
- Khi xử lý phần giao diện, phải ưu tiên classless, SUDS, và hệ thống template hiện có của dự án.
- Chỉnh sửa tối giản:
  - mỗi phase chỉ sửa đúng điểm cần thiết
  - không mở rộng phạm vi refactor ngoài kế hoạch phase
  - ưu tiên thay đổi nhỏ, có thể đảo ngược
- Với file đã tồn tại:
  - không thay toàn bộ nội dung nếu không thật sự bắt buộc
  - ưu tiên thay đúng vùng cần sửa bằng kỹ thuật thay thế tối thiểu
- Sau mỗi phase phải kiểm tra hệ thống còn hoạt động.
- Không tự động commit.
- Không tự động tạo changelog.
- Chỉ commit hoặc cập nhật changelog khi có yêu cầu cụ thể.

## Chuẩn kiểm tra sau mỗi phase

Sau mỗi phase, người thực hiện phải làm tối thiểu các bước sau:

1. Kiểm tra file vừa sửa có import hoặc parse được.
2. Chạy smoke check phù hợp với phạm vi phase.
3. Xác nhận CLI hoặc WebUI vẫn boot được nếu phase có đụng vào chúng.
4. Ghi rõ kết quả kiểm tra vào artifact hoặc báo cáo phase.

## Mẫu thực thi từng phase

Trước khi thực hiện bất kỳ phase nào, phải tạo execution note theo mẫu:

- [phase-execution-template.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/phase-execution-template.md)

Execution note là hợp đồng nhỏ cho một lượt làm việc cụ thể. Nó phải ghi rõ:

- phase đang thực hiện
- file được phép chạm
- symbol cần chạy GitNexus impact
- thay đổi dự kiến
- smoke check bắt buộc
- điều kiện rollback hoặc dừng

Không bắt đầu sửa code nếu execution note chưa có đủ các mục trên.

## Chuẩn chỉnh sửa tối thiểu

Để tránh làm dự án mất ổn định, mọi phase phải tuân theo chiến lược sửa mã sau:

1. Đọc symbol hiện có qua GitNexus hoặc code hiện hành trước khi sửa.
2. Xác định đúng hàm, class, route, hoặc file cần chạm.
3. Chỉ sửa đúng vùng code phục vụ mục tiêu phase.
4. Không dọn dẹp lan man.
5. Không đổi tên lớn nếu phase đó không chuyên về rename hoặc extraction.

## Thứ tự thực hiện

0. [phase-execution-template.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/phase-execution-template.md)
1. [01-phase-baseline-inventory.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/01-phase-baseline-inventory.md)
2. [02-phase-test-harness-and-safety-net.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/02-phase-test-harness-and-safety-net.md)
3. [03-phase-backend-scaffold.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/03-phase-backend-scaffold.md)
4. [04-phase-config-and-key-services.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/04-phase-config-and-key-services.md)
5. [05-phase-prompt-provider-model-services.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/05-phase-prompt-provider-model-services.md)
6. [06-phase-workspace-project-bootstrap-services.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/06-phase-workspace-project-bootstrap-services.md)
7. [07-phase-progress-event-contract.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/07-phase-progress-event-contract.md)
8. [08-phase-translation-usecase-shell.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/08-phase-translation-usecase-shell.md)
9. [09-phase-cli-decoupling.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/09-phase-cli-decoupling.md)
10. [10-phase-webui-translation-route-refactor.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/10-phase-webui-translation-route-refactor.md)
11. [11-phase-project-translation-usecase.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/11-phase-project-translation-usecase.md)
12. [12-phase-spellcheck-usecase.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/12-phase-spellcheck-usecase.md)
13. [13-phase-project-service-decomposition.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13-phase-project-service-decomposition.md)
14. [14-phase-settings-prompts-and-plugin-services.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/14-phase-settings-prompts-and-plugin-services.md)
15. [15-phase-webui-state-frontend-modularization.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/15-phase-webui-state-frontend-modularization.md)

## Sub-plan bắt buộc cho Phase 13

Phase 13 rất lớn, nên không được thực hiện trực tiếp từ file tổng. Phải đi qua các sub-plan sau:

1. [13a-project-crud-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13a-project-crud-service-plan.md)
2. [13b-project-file-operations-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13b-project-file-operations-service-plan.md)
3. [13c-project-prompts-assets-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13c-project-prompts-assets-service-plan.md)
4. [13d-project-archive-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13d-project-archive-service-plan.md)
5. [13e-project-translation-memory-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13e-project-translation-memory-service-plan.md)

## Định nghĩa hoàn tất toàn chương trình

Chương trình tách lớp chỉ được xem là xong khi:

- CLI không còn gọi `main.py` bằng cách sửa `sys.argv`.
- `main.py` không còn là nơi chứa orchestration chính.
- `core/executor.py` không import gì từ `webui/`.
- `webui/routes/*.py` chỉ còn transport/controller mỏng.
- Prompt/config/provider/workspace/project operations đều đi qua backend dùng chung.
- Một bugfix nghiệp vụ translation hoặc spellcheck chỉ sửa ở backend core.
