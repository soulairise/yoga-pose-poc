# 검증에 쓴 영상의 출처와 라이선스

> 확인일: **2026-08-12** (Wikimedia Commons API `extmetadata` 로 확인)
> 영상 파일은 저장소에 커밋하지 않습니다. `python src/fetch_data.py` 로 받으십시오.

---

## 왜 직접 촬영한 영상이 아닌가

이 PoC의 대상은 **회원의 몸이 찍힌 영상**입니다. 그런 자료는

- 저장소에 커밋할 수 없고 (개인정보),
- 제3자가 클론해서 **같은 결과를 재현할 수 없습니다.**

그래서 **검증용으로는 자유 라이선스로 공개된 스쿼트 영상**을 썼습니다.
무릎을 굽혔다 펴는 관절 구조가 웃카타아사나와 같아 판정 로직을 그대로 시험할 수 있고,
누구나 같은 파일을 받아 **같은 숫자를 재현**할 수 있습니다.

> ⚠️ 이 선택의 한계는 `docs/04_한계와_다음단계.md` 에 적어 두었습니다.
> 특히 **시연 영상에는 "충분히 앉지 않은 회차"가 없어 성공 기준 S2를 평가할 수 없었습니다.**

---

## 목록

| 파일 | 원본 | 라이선스 | 저작자 |
|---|---|---|---|
| `cc01_squat_demo.webm` | [File:Squat - exercise demonstration video.webm](https://commons.wikimedia.org/wiki/File:Squat_-_exercise_demonstration_video.webm) | **CC BY 3.0** | Scott Webb (via Wikimedia Commons) |
| `cc02_squat_frontal_raise.webm` | [File:Squat and Frontal Raise.webm](https://commons.wikimedia.org/wiki/File:Squat_and_Frontal_Raise.webm) | **CC BY-SA 4.0** | User:Taco fleur |
| `cc03_single_leg_squat.webm` | [File:Basic single leg squat.webm](https://commons.wikimedia.org/wiki/File:Basic_single_leg_squat.webm) | **CC BY-SA 4.0** | User:RickyBennison |

### 파일 무결성 (sha256)

```
cc01_squat_demo.webm          2440985661c3533a4ce78472b0f4577dbdf023aff3f8f9a225bbb5ff8071b1e9
cc02_squat_frontal_raise.webm 18c66dcb8323d14a8e0197ea4f379e609b068d9b2cd2233d8b60d8fa5d26fb02
cc03_single_leg_squat.webm    ab4602823ad00de3409eb50d2c65c6b1ce5566c5dca6753555ff2b19107db88e
```

---

## 각 영상의 성격

| 파일 | 촬영 | 길이 | 특징 | 이 자료를 넣은 이유 |
|---|---|---|---|---|
| `cc01` | 후측면·고정 | 7.1초 | 바벨 백스쿼트, 실내, 720p | **기본 조건** — 깊이 앉고 완전히 펴는 표준 동작 |
| `cc02` | 측면·고정 | 28.2초 | 케틀벨 동작, 반복이 많음 | **긴 영상** — 반복이 여러 번일 때 누적 오차가 있는지 |
| `cc03` | 측면·원거리 | 7.8초 | **한쪽 다리** 스쿼트, 야외, 인물이 작음 | **어려운 것** — 동작이 다르고 인물이 작다 |

> `cc03`은 일부러 **다른 동작**을 넣은 것입니다.
> 쉬운 것만 모으면 후보들이 전부 비슷해 보이고 표가 아무것도 알려 주지 않습니다.
> 실제로 이 영상에서 기본 임계값이 무너졌고, 그것이 이 PoC의 가장 중요한 발견이 되었습니다.

---

## 라이선스 준수

- **CC BY 3.0 / CC BY-SA 4.0** 모두 출처 표시 조건입니다. 위 표에 저작자와 원본 주소를 적었습니다.
- 이 저장소는 영상 파일을 **재배포하지 않습니다** (`.gitignore`). 내려받기 주소만 제공합니다.
- CC BY-SA 4.0의 동일조건변경허락(share-alike)은 **영상의 2차적 저작물**에 걸립니다.
  이 저장소가 배포하는 것은 **코드와 수치 결과**이며 영상 자체나 그 파생물이 아닙니다.
  `results/**/*.mp4`(관절을 그린 영상)는 영상의 파생물에 해당하므로 **커밋하지 않습니다.**
