"use client";

import {
  Activity,
  BookOpen,
  Box,
  Brain,
  Building2,
  Code2,
  Compass,
  Cpu,
  Database,
  Download,
  Droplets,
  FlaskConical,
  Gauge,
  Globe2,
  Landmark,
  Layers,
  Mail,
  MapPin,
  MapPinned,
  Mountain,
  Radar,
  Radio,
  Satellite,
  Server,
  Shield,
  ShieldCheck,
  Sparkles,
  Target,
  Terminal,
  Users,
  Zap,
} from "lucide-react";
import { IconOrb, type IconOrbProps } from "@/components/visuals/IconOrb";

const ICONS = {
  activity: Activity,
  bookOpen: BookOpen,
  box: Box,
  brain: Brain,
  building2: Building2,
  code2: Code2,
  compass: Compass,
  cpu: Cpu,
  database: Database,
  download: Download,
  droplets: Droplets,
  flask: FlaskConical,
  gauge: Gauge,
  globe2: Globe2,
  landmark: Landmark,
  layers: Layers,
  mail: Mail,
  mapPin: MapPin,
  mapPinned: MapPinned,
  mountain: Mountain,
  radar: Radar,
  radio: Radio,
  satellite: Satellite,
  server: Server,
  shield: Shield,
  shieldCheck: ShieldCheck,
  sparkles: Sparkles,
  target: Target,
  terminal: Terminal,
  users: Users,
  zap: Zap,
} as const;

export type IconName = keyof typeof ICONS;

type IconOrbStaticProps = Omit<IconOrbProps, "icon"> & {
  name: IconName;
};

export function IconOrbStatic({ name, ...props }: IconOrbStaticProps) {
  return <IconOrb icon={ICONS[name]} {...props} />;
}
