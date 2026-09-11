## Hard Constraints
- When modifying kernel DT or .ko files, must delete `device/qcom/kalama-kernel/Image` to force kp-dtbs refresh during incremental compilation
- Device tree overlay files with identical board-id will be selected by UEFI in the order they appear in dtbo.img
- Both `kalamap-hdk-overlay.dts` (main overlay) and `kalamap-hdk-overlay-gpiotest.dts` (factory test overlay) must be modified to ensure SSD enumeration works in all boot modes
- QCS8550 has two independent PCIe Root Complexes (RC0 and RC1), where RC0 is used for WiFi and RC1 for M.2 NVMe SSD
- PCIe controllers in QCS8550 use on-demand link training; RC1 requires a client driver to trigger enumeration
- GPIO46 must be configured with `gpio-hog output-high` in device tree to provide 3.3V power to M.2 SSD slot
- `pcie1` node in device tree must set `qcom,boot-option = <0x0>` to enable automatic RC1 enumeration at boot
- `/vendor/etc/fstab.qcom` must include `voldmanaged=nvme:auto` entry to enable automatic mounting of M.2 NVMe SSD as portable storage
- Code changes must be submitted via Pull Request (PR) on Gitea; verbal notification alone is insufficient
- PRs should target merging feature branches into the `master` branch
- Local feature branches should not be deleted until PR is merged and verified in `master`
- Gitea PRs must include clear title/description matching the commit message
- Gitea account 981637988 is used for repository access and PR creation
- PRs require approval and merging by team member xfding
- Remote feature branches may be deleted after successful PR merge (optional)
- 记忆必须同步到项目备份目录：每次存了新记忆后，把 `c:\Users\123456\.trae-cn\memory\projects\-d-win-game-project--p2-ea3144bba63d4aa9444e\`（project_memory.md + 按日期文件夹）和 `user_profile.md` 镜像拷贝到 `D:\win_game_project\03_ai的记忆_和skill\01_记忆原档\` 对应位置；重大进展还要更新 `02_知识库_整理版.md` 的当前状态章节

## Engineering Conventions
- Device tree modifications follow two patterns: adding new overlay files with unique oem-id or modifying existing overlay files
- Git commits for device tree changes must precisely add only the modified .dts files, avoiding `git add -A` to prevent including build artifacts
- Feature branches should be named descriptively (e.g., `ssd-m2-nvme`)
- Local branches should set upstream tracking to remote feature branches using `git branch -u gitea/[branch-name]`

## Lessons Learned
- Incremental compilation may skip copying updated DT files if `Image` exists and build.config is unchanged, leading to outdated dtbo.img
- gpiotest overlay entries in dtbo.img appear before main overlay entries, causing UEFI to prioritize them when board-ids match
- Without GPIO46 power and RC1 enumeration trigger, M.2 SSD will not be detected even if physically connected
- `git push` alone only uploads code to remote; PR creation is required to formally request code review and merge
- Gitea中 WIP、Draft、Open 是三个不同维度：WIP只是标题文字前缀(无机制作用)；Draft是真状态(无合并按钮，需点"Ready for review"转正)；Open才是可合并的正式状态
- 创建PR时Gitea默认可勾选"以草稿形式创建"，导致PR同时带 WIP 标题前缀 + draft=true，页面看起来"又WIP又草稿"
- Gitea API 可程序化转换PR状态：`PATCH /api/v1/repos/{owner}/{repo}/pulls/{index}`，body 传 `{"draft": false}` 转正式、`{"title":"..."}` 可同时去掉WIP前缀；账号981637988对该仓库有 push 权限可执行
- 在Windows PowerShell里 `curl` 是 Invoke-WebRequest 别名，调用API要用 `curl.exe`；且内联JSON易被PowerShell转义破坏，改写入临时文件后用 `-d @文件路径` 避免
- 账号981637988查询PR详情API：`GET /api/v1/repos/xfding/LA.VENDOR.15.4.3-irix/pulls/{index}`，返回字段含 draft/state/mergeable/title，可据此判断PR状态
- SNM970/OK700掌机固件pmic_glink/充电栈残缺导致OTG VBUS 5V供电缺失，手柄无法枚举；表现为/sys/class/power_supply/无battery节点、dumpsys battery present=false、开机日志"msm_eusb2_phy: Could not get usb phy"
- 强制切换USB角色或重绑xhci驱动无法解决掌机OTG供电问题，需修复固件电池管理栈
- 中文WiFi SSID通过adb连接时需使用`connect-network -x`参数传入UTF-8 hex编码，直接传输会因编码问题连接失败
- SNM970硬件事实（同事09-06拍板）：3.5mm耳机口物理不通；坏的是tinyALSA/PAL层（SPEAKER HAL write永久阻塞，AudioOut_D线程Total writes=4/Blocked=yes卡死，30+条config event堆积），AudioFlinger框架层是好的
- 安卓雷云捕获路线09-06大切换：AudioPlaybackCapture/REMOTE_SUBMIX影子轨路在QCOM BSP上已实测不通；新路线=蓝牙A2DP出声（独立HAL不碰tinyalsa，是数据流动的引擎）+ AudioFlinger per-track hook（Track::getNextBuffer混音前抄游戏轨原始PCM→Unix socket给HapticX，usage=GAME过滤）
- AF输出的所有轨数据都靠输出线程threadLoop"拉"出来；primary卡死时挂在它上面的轨道数据不流，任何hook都无数据——蓝牙A2DP混音线程正常循环是取数硬前提
- audioflinger/audiopolicy都在QSSI树system侧（frameworks/av/services/），单模块增量编译+push .so+killall audioserver分钟级迭代（build_apm.sh套路），不需要6h整包
- 设备实际加载的音频策略配置：/vendor/etc/audio/sku_kalama_qssi/audio_policy_configuration.xml（不是sku_kalama_apc.xml）；09-05晚推过修改版（删Speaker attach+默认输出改Wired Headphones）后重启设备掉线未归，恢复在线后第一件事回滚到原版（备份在D:\win_game_project\.workbuddy\tmp_apmcheck\apc_device.xml）