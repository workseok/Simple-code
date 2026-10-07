# 매팅 엔진 가이드 (BackgroundMattingV2 · MODNet · RobustVideoMatting)

BG Matte는 인물을 분리하는 **엔진**을 설정에서 고를 수 있습니다. 엔진만 다르고 배경 합성, 번호 배경(1~9),
알파 보기, 전체 화면, 테마, 설정 저장은 모두 같습니다.

| | BackgroundMattingV2 (기본) | MODNet | RobustVideoMatting (RVM) |
| --- | --- | --- | --- |
| 방식 | 빈 배경 사진과 현재 화면의 **차이**로 분리 | 화면 한 장만 보고 **인물**을 분리 | 이전 프레임 기억을 이어받는 **영상** 분리 |
| 빈 배경 촬영 | **필요** (스페이스바), 촬영 뒤 카메라 고정 | 불필요 | 불필요 |
| 분리 대상 | 배경과 달라진 모든 것 (의자·소품 포함) | **사람만** (의자는 빠짐) | **사람만** |
| 카메라 이동 | 불가 (빈 배경이 어긋남) | 가능 | 가능 |
| 깜빡임 대책 | 필요 없음 | 설정의 '깜빡임 줄이기'(시간축 스무딩) | 모델 자체가 프레임 간 기억 사용 |
| 가중치 | `pytorch_*.pth` (백본별) | `modnet_webcam_portrait_matting.ckpt` | `rvm_mobilenetv3.pth` / `rvm_resnet50.pth` |
| 코드 라이선스 | MIT | Apache 2.0 | **GPL-3.0** |

> 속도와 품질은 컴퓨터마다 크게 다르므로 표에 숫자를 적지 않았습니다. 같은 자리, 같은 조명에서 엔진을 바꿔
> 가며 화면 오른쪽의 **FPS**와 **알파 보기(A 키)** 로 직접 비교하세요.
> 상업 용도라면 코드 라이선스와 별개로 **가중치·학습 데이터 약관**을 따로 확인해야 합니다. RVM은 GPL-3.0이라
> 코드를 제품에 넣어 배포하는 경우 소스 공개 의무가 생길 수 있습니다.

## 1. 설치 (인텔 맥)

앱을 쓰는 conda 환경을 켠 상태에서, 프로젝트 폴더에서 실행합니다.

```bash
cd ~/Simple-code            # 프로젝트 폴더 (실제 위치에 맞게)
conda activate bgmatte      # 앱을 쓰는 환경 이름
bash packaging/install_engines.sh          # MODNet + RVM(mobilenetv3) 한 번에
```

- 일부만 설치: `bash packaging/install_engines.sh modnet` / `rvm` / `rvm50`(RVM resnet50 가중치 108MB)
- 코드는 프로젝트 폴더 **옆**(`../MODNet`, `../RobustVideoMatting`)에, 가중치는 `models/`에 저장됩니다.
  설정 화면의 기본값이 이 위치와 같아서 따로 지정할 필요가 없습니다.
- 여러 번 실행해도 안전합니다. 이미 받은 파일은 건너뜁니다.

### 직접 받기 (스크립트가 실패할 때)

- MODNet 가중치: 브라우저로 <https://drive.google.com/drive/folders/1umYmlCulvIFNaqPjwod1SayFmSRHziyR> 를 열어
  `modnet_webcam_portrait_matting.ckpt` 를 받아 `models/` 에 넣습니다. 코드는 `git clone https://github.com/ZHKKKe/MODNet.git ../MODNet`
- RVM 가중치: <https://github.com/PeterL1n/RobustVideoMatting/releases/tag/v1.0.0> 에서 `rvm_mobilenetv3.pth`(15MB)
  또는 `rvm_resnet50.pth`(108MB). 코드는 `git clone https://github.com/PeterL1n/RobustVideoMatting.git ../RobustVideoMatting`

## 2. 사용

1. 앱의 **설정 → 매팅 엔진**에서 MODNet 또는 RobustVideoMatting을 고르고 **저장**합니다. 실행 중이면 자동으로 다시 시작됩니다.
2. 오른쪽 **상태** 패널의 '엔진' 줄에 현재 엔진이 표시됩니다.
3. MODNet / RVM은 **빈 배경 촬영 없이** 바로 합성됩니다. '배경 촬영' 버튼과 스페이스바는 이 엔진들에서는 꺼집니다.
4. 합성 배경 번호 키(1~9), A(알파 보기), 전체 화면 등은 엔진과 관계없이 똑같이 동작합니다.

### 속도가 느릴 때 (인텔 맥은 CPU로 처리합니다)

| 엔진 | 설정 | 효과 |
| --- | --- | --- |
| MODNet | 처리 해상도 `256` (기본) | 선택지 중 가장 빠름. 높일수록 정밀해지고 느려짐 |
| MODNet | 깜빡임 줄이기 `꺼짐` | 속도 차이는 거의 없고, 경계가 더 떨림 |
| RVM | 처리 비율 `0.25` | 가장 빠름 (머리카락 디테일 감소) |
| RVM | 종류 `mobilenetv3` | resnet50보다 훨씬 가볍습니다 |
| 공통 | 설정의 카메라 해상도를 1280×720으로 | 처리할 화소 수가 줄어듦 |

### 품질이 아쉬울 때

- MODNet: 처리 해상도 `384` / `512`, '깜빡임 줄이기'를 `약`~`보통`으로 조절합니다. 너무 세게 하면 빠른 움직임에서 잔상이 생깁니다.
- RVM: 처리 비율 `0.5` / `0.75`, 종류 `resnet50`. 화면이 이상하게 굳으면 정지 후 다시 시작해 기억을 초기화합니다.
- 사람 외의 물체(의자 등)까지 합성해야 한다면 MODNet/RVM으로는 불가능합니다. BackgroundMattingV2를 쓰세요.

## 3. 문제 해결

| 증상 | 원인 / 해결 |
| --- | --- |
| "MODNet(또는 RVM) 코드 폴더를 찾을 수 없습니다" | `install_engines.sh`를 실행했는지, 설정의 '코드 폴더'가 맞는지 확인 |
| "가중치 파일이 없습니다" | `models/` 안의 파일 이름이 설정 화면과 같은지 확인. RVM은 종류(mobilenetv3/resnet50)별로 파일이 따로 필요 |
| "모델을 불러오지 못했습니다" | 가중치와 종류가 다른 경우(예: 종류는 resnet50인데 mobilenetv3 파일). 설정의 종류 칸 확인 |
| 인물 일부가 투명하게 나옴 | 해당 엔진의 한계일 수 있습니다. 알파 보기로 마스크를 먼저 확인하고 처리 해상도/비율을 올려 보세요 |
| BackgroundMattingV2로 되돌리고 싶음 | 설정 → 매팅 엔진 → BackgroundMattingV2. 기존 `bgr.png`와 가중치 설정은 그대로 남아 있습니다 |

## 4. 구조와 윈도우 확장

- **엔진 인터페이스**: `bgmatte_app/matte_core.py`의 엔진 클래스는 입력 한 장(`src`, RGB, 0~1)을 받아 `(알파, 전경색 또는 None)`을
  돌려주는 `infer()`만 구현하면 됩니다. 합성, 배경 전환, 알파 보기, 장치 선택, GPU 실패 시 CPU 전환은 공통 코드(`Matter`)가 맡습니다.
- 새 엔진을 추가하려면 ① `config.py`의 `ENGINES`와 설정 항목, ② `matte_core.py`의 로더와 엔진 클래스를 `_LOADERS`에 등록,
  ③ 설정 화면 칸(`dialogs.py`)을 추가합니다. 워커와 화면 코드는 건드리지 않아도 됩니다.
- **같은 이름의 패키지 충돌 방지**: BackgroundMattingV2와 RVM은 모두 `model`이라는 패키지를 씁니다. 엔진을 불러올 때 해당 이름의
  모듈 캐시를 잠시 치우고 그 저장소만 경로 맨 앞에 두는 방식(`_isolated_import`)이라, 앱을 끄지 않고 엔진을 바꿔도 섞이지 않습니다.
- **윈도우**: 설치와 사용은 `docs/APP_WINDOWS.md`를 보세요. 준비 상태 (아직 윈도우 PC에서 실행해 확인하지는 않았습니다):
  - 장치 선택은 이미 `cuda → mps → cpu` 순이라 NVIDIA GPU가 있으면 자동으로 씁니다.
  - 카메라는 윈도우에서 DirectShow(`CAP_DSHOW`)로 엽니다. 설정 폴더는 `~/.config/BGMatte`, 로그는 `~/.cache/BGMatte`입니다.
  - 카메라 권한 안내 버튼은 윈도우에서 '개인정보 → 카메라' 설정 창(`ms-settings:privacy-webcam`)을 엽니다.
  - 설치 스크립트(`install_engines.sh`)는 Git Bash에서 그대로 실행됩니다. `.app` 번들은 맥 전용이므로 윈도우에서는
    `python -m bgmatte_app`으로 실행합니다. (`docs/SETUP_WINDOWS.md` 참고)
  - 방송 시스템 이식이 목표라면 다음 단계로 MODNet의 ONNX/TensorRT, RVM의 ONNX 변환판(공식 배포)을 엔진 클래스로 추가하는 것이 가장 짧은 길입니다.
    (TensorRT는 NVIDIA GPU 전용이라 맥에서는 쓸 수 없습니다.)
