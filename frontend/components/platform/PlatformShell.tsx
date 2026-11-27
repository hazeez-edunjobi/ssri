"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { BrandLockup } from "@/components/landing/BrandMark";
import { LandPhoto } from "@/components/theme/LandPhoto";
import {
  LOCAL_ACCEPTANCE_EMAIL,
  localAcceptanceSessionAllowed,
} from "@/lib/localAcceptanceSession";
import { getSupabase, supabaseConfig } from "@/lib/supabase";
import type { UnsplashKey } from "@/lib/visuals";
import { cn } from "@/lib/utils";
import { Loader } from "@/components/ui/loader";

const LINKS = [
  { href: "/workspace", label: "Dashboard" },
  { href: "/datasets", label: "Datasets" },
  { href: "/geological", label: "Geological" },
  { href: "/training", label: "Training" },
  { href: "/models", label: "Models" },
  { href: "/assessments", label: "Assessments" },
  { href: "/validation", label: "Validation" },
  { href: "/activity", label: "Activity" },
  { href: "/dashboard", label: "Assessment map" },
];

const BANNERS: Array<{
  prefix: string;
  unsplash: UnsplashKey;
  alt: string;
  caption: string;
}> = [
  {
    prefix: "/admin",
    unsplash: "forest",
    alt: "Forest canopy over uneven ground",
    caption: "Look after the platform",
  },
  {
    prefix: "/datasets",
    unsplash: "farmland",
    alt: "Aerial crop fields used as land data",
    caption: "Land, packaged for training",
  },
  {
    prefix: "/geological",
    unsplash: "geology",
    alt: "Exposed rock layers and ground structure",
    caption: "Client geological layers",
  },
  {
    prefix: "/training",
    unsplash: "geology",
    alt: "Mountain ridges and valleys",
    caption: "Train on real terrain",
  },
  {
    prefix: "/models",
    unsplash: "satellite",
    alt: "Satellite view of mountains and green valleys",
    caption: "Versions of the ground model",
  },
  {
    prefix: "/assessments",
    unsplash: "satellite",
    alt: "Satellite view of terrain used for ground assessment",
    caption: "Past map assessments",
  },
  {
    prefix: "/activity",
    unsplash: "landscape",
    alt: "Green valley landscape",
    caption: "What changed on your account",
  },
  {
    prefix: "/workspace",
    unsplash: "hills",
    alt: "Rolling green hills",
    caption: "Your ground-risk workspace",
  },
];

function bannerFor(pathname: string) {
  return BANNERS.find((item) => pathname.startsWith(item.prefix)) ?? BANNERS[BANNERS.length - 1];
}

export function PlatformShell({
  children,
  admin = false,
}: {
  children: React.ReactNode;
  admin?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const configured = supabaseConfig().configured;
  const localAcceptance = localAcceptanceSessionAllowed();
  const [ready, setReady] = useState(() => localAcceptance);
  const [email, setEmail] = useState<string | null>(() =>
    localAcceptance ? LOCAL_ACCEPTANCE_EMAIL : null,
  );
  const banner = bannerFor(pathname || "/workspace");

  useEffect(() => {
    if (localAcceptance) {
      return;
    }
    const supabase = getSupabase();
    if (!supabase) {
      // Unconfigured environments render the "Sign-in is not configured"
      // panel below before `ready` is ever consulted, so nothing to sync.
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace(`/login?next=${encodeURIComponent(pathname || "/workspace")}`);
        return;
      }
      setEmail(data.session.user.email ?? null);
      setReady(true);
    });
  }, [pathname, router, localAcceptance]);

  if (!configured) {
    return (
      <main className="min-h-screen bg-mist px-6 py-16 text-bark">
        <div className="mx-auto max-w-lg rounded-3xl border border-meadow bg-chalk p-6 text-sm shadow-soft">
          <h1 className="font-display text-xl">Sign-in is not configured</h1>
          <p className="mt-3 text-stone">
            Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, then apply the
            Version 4 database migration.
          </p>
          <Link href="/login" className="mt-4 inline-block font-semibold text-moss">
            Go to login
          </Link>
        </div>
      </main>
    );
  }

  if (!ready) {
    return (
      <main className="min-h-screen bg-mist">
        <Loader
          variant="page"
          title="Checking session"
          description="Confirming your signed-in workspace before continuing."
          data-testid="platform-shell-loading"
        />
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-mist text-bark">
      <header className="sticky top-0 z-40 border-b border-meadow bg-chalk/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-4 px-4 py-3">
          <BrandLockup />
          <nav className="flex flex-wrap gap-1 text-sm">
            {LINKS.map((link) => {
              const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "rounded-md px-3 py-2 font-medium",
                    active ? "text-moss" : "text-stone hover:text-canopy"
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
            {admin && (
              <Link
                href="/admin"
                className={cn(
                  "rounded-md px-3 py-2 font-medium",
                  pathname.startsWith("/admin") ? "text-moss" : "text-stone hover:text-canopy"
                )}
              >
                Admin
              </Link>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-xs text-stone">
            <span className="max-w-[180px] truncate">{email}</span>
            <button
              type="button"
              className="font-semibold text-moss"
              onClick={async () => {
                await getSupabase()?.auth.signOut();
                router.replace("/login");
              }}
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-[1200px] px-4 py-8">
        <LandPhoto unsplash={banner.unsplash} alt={banner.alt} caption={banner.caption} className="mb-8" />
        {children}
      </div>
    </div>
  );
}
