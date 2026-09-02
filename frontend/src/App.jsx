import { useState } from "react";
import "./App.css";
import MobileLayout from "./components/layout/MobileLayout";
import Header from "./components/common/Header";
import Input from "./components/common/Input";
import Button from "./components/common/Button";

function App() {
  const [count, setCount] = useState(0);

  return (
    <MobileLayout>
      <Header
        title="지역을 선택해 주세요"
        subtitle={
          <div>
            선택한 지역의 분리배출 기준으로 안내해 드립니다.
            <br />한 번 설정하면 다음 방문 시 자동 적용됩니다.
          </div>
        }
      />
      <Input label="지역 선택" placeholder="지역을 선택해 주세요" />
      <Button>확인</Button>
    </MobileLayout>
  );
}

export default App;
