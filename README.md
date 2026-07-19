# ops-agent-app

에이전트(Hermes)가 운영하는 EC2에 올라가는 데모 앱 코드. 인프라 리포
[`ops-agent-iac`](https://github.com/wo-o/ops-agent-iac)와 짝을 이룬다. 인프라
정의(`*.tf`)와 애플리케이션 코드를 분리하기 위해 별도 리포로 뺐다.

시크릿이 전혀 없어 퍼블릭으로 공개해도 안전하다 — DB 접속 정보는 이 리포가
아니라 인프라(Terraform user_data)가 호스트에 써주는 `/opt/app/env`에서만 온다.

## 구성

| 파일 | 역할 |
| --- | --- |
| `app.py` | RDS(PostgreSQL)를 쓰는 가벼운 stdlib HTTP API. `:8080`에서 뜬다. |
| `app.service` | systemd unit. `/opt/app/env`를 EnvironmentFile로 읽는다. |
| `install.sh` | 의존성 설치 + `app.py`·unit 배치 + `systemctl enable --now`. |

## 엔드포인트

| 경로 | 동작 |
| --- | --- |
| `GET /healthz` | 200 (ALB health check, DB 불필요) |
| `GET /` | 200 서비스 정보 + DB 연결 상태 |
| `GET /items` | items SELECT (JSON) |
| `POST /items` | items INSERT (body=name) |
| `GET /troublemaker` | 사전 장애: DB 커넥션 누수 + CPU 소모 + ERROR 로그 → 500 |
| `GET /leak?mb=N` | 사전 장애: 프로세스 메모리 ballast +N MB (1..500, 기본 100) → 200. 재시작으로만 해제 — memory 알람 주입용 |

로그: `/var/log/app/app.log` (promtail이 있으면 `job=app`).

## 배포 (인프라 리포와의 계약)

EC2 부팅 시 `ops-agent-iac`의 `app.tf` user_data가:

1. `git`을 설치하고
2. 시크릿 env 파일 `/opt/app/env`를 작성한 뒤 (DB_HOST·비번은 Terraform만 아는 값)
3. 이 리포를 **태그에 pin**해서 clone하고
4. `install.sh`를 실행한다.

```bash
apt-get install -y git
git clone --depth 1 --branch "$APP_VERSION" \
  https://github.com/wo-o/ops-agent-app.git /tmp/ops-agent-app
bash /tmp/ops-agent-app/install.sh
```

브랜치가 아니라 태그(예: `v1`)에 pin하므로, 같은 launch template로 언제
띄우든 동일한 코드가 뜬다(재현성).

### 실서비스라면

부팅 시점에 GitHub에서 코드를 당겨오는 방식은 부팅이 외부 네트워크에
의존하고 무버전 fetch면 롤백이 어렵다. 프로덕션에서는 여기서 코드까지 구운
**불변 이미지**(Packer로 baked AMI, 또는 컨테이너 이미지)를 만들어 EC2가 그
이미지로만 뜨게 한다. 이 리포의 태그 pin 방식은 강의용 절충안이다.
