import { SiteShell } from "@/components/layout/SiteShell";
import { Reveal } from "@/components/animations/Reveal";
import { Hero } from "@/components/landing/Hero";
import { PlatformSurfaces } from "@/components/landing/PlatformSurfaces";
import { CorePlatform } from "@/components/landing/CorePlatform";
import { EverydayUses } from "@/components/landing/EverydayUses";
import { CapabilityGrid } from "@/components/landing/CapabilityGrid";
import { BuiltForWork } from "@/components/landing/BuiltForWork";

export default function Home() {
  return (
    <SiteShell>
      <main>
        <Hero />
        <Reveal>
          <PlatformSurfaces />
        </Reveal>
        <Reveal>
          <CorePlatform />
        </Reveal>
        <Reveal>
          <EverydayUses />
        </Reveal>
        <Reveal>
          <CapabilityGrid />
        </Reveal>
        <Reveal>
          <BuiltForWork />
        </Reveal>
      </main>
    </SiteShell>
  );
}
