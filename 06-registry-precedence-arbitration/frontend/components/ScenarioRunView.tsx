"use client";

import { useCallback, useState } from "react";
import type { Scenario } from "@/lib/types";
import ClaimRunCard from "./ClaimRunCard";
import RegistryPanel from "./RegistryPanel";
import ChatBox from "./ChatBox";

export default function ScenarioRunView({ scenario }: { scenario: Scenario }) {
  const [completedCount, setCompletedCount] = useState(0);
  const [registryRefreshToken, setRegistryRefreshToken] = useState(0);

  const bumpRegistry = useCallback(() => setRegistryRefreshToken((n) => n + 1), []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
      <div className="space-y-4">
        {scenario.claims.map((claim, i) => (
          <ClaimRunCard
            key={claim.key}
            claim={claim}
            order={i + 1}
            enabled={i <= completedCount}
            onDone={() => setCompletedCount((c) => Math.max(c, i + 1))}
            onActivity={bumpRegistry}
          />
        ))}

        <ChatBox sku={scenario.claims[0]?.sku} />
      </div>

      <RegistryPanel refreshToken={registryRefreshToken} />
    </div>
  );
}
