[ ICON CLI tool 설치 및 사용법 ]

ICON CLI tool 의 설치 방법 및 사용법은 github의 README에서 제공하고 있습니다.

<https://github.com/icon-project/icon_cli_tool>



[ ICX 이체 테스트 방법 ]

1. ICX를 송금할 keystore file, 송금 받을 keystore file 를 생성

 - wallet 명령어 중, wallet create 사용

   ```shell
   # command
   $ icli wallet create <file path> -p <password>
   ```

   ``` shell
   # example
   # 송금할 keystore file 생성
   $ icli wallet create ./test_wallet_sending_icx -p abcd1234*

   # result
   Succeed to create wallet in ./test_wallet_sending_icx.
   Wallet address : hx85ad76ec22c77faeea059e635a0d9d1fca74c62f

   # 송금받을 keystore file 생성
   $ icli wallet create ./test_wallet_receiving_icx -p abcd1234*

   # result
   Succeed to create wallet in ./test_wallet_receiving_icx.
   Wallet address : hx20c78cd02f1362bbcc1fa6492e0e38a006d326d6
   ```

2. ICX 이체

- wallet 명령어 중, transfer 사용

  - 송금을 위해서는 위에서 생성한 송금할 keystore file에  ICX 를 보유하고 있어야 합니다.
  - 따라서, 위에서 생성한 송금할 keystore file의 지갑 주소 알려주시면 테스트를 위한 ICX를 해당 지갑으로 송금해드리겠습니다.
  - n 옵션에 시티즌 노드 주소를 입력하시면 됩니다.

  ``` shell
  # command
  $ icli transfer <to> <amount> <file path> -p <password> -f <fee=10000000000000000> | -n <network id: mainnet | testnet | IP or domain>
  ```

  ```shell
  # example
  $ icli transfer hx20c78cd02f1362bbcc1fa6492e0e38a006d326d6 320000000000000000 ./test_wallet_sending_icx -p abcd1234* -n http://localhost:9000/api/v2

  # result
  Transaction has been completed successfully.
  ```


3. 잔고 조회

- wallet 명령어 중, asset list 사용

  ```shell
  # command
  $ icli asset list <file path> -p <password> | -n <network id: mainnet | testnet | IP or domain>
  ```

  ```shell
  # example
  $ icli asset list ./test_wallet_receiving_icx -p abcd1234* -n http://localhost:9000/api/v2

  # result
  Wallet address : hx20c78cd02f1362bbcc1fa6492e0e38a006d326d6
  Wallet balance : 320000000000000000 loop
  ```