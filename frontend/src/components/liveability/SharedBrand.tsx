"use client";

import { motion } from "framer-motion";
import Image from "next/image";

type SharedBrandProps = {
  compact?: boolean;
};

export function SharedBrand({ compact = false }: SharedBrandProps) {
  return (
    <motion.div layoutId="brand-shell" className="flex items-center">
      <motion.div
        layoutId="brand-icon"
        className={`relative overflow-hidden ${compact ? "h-8 w-28" : "h-9 w-32"}`}
      >
        <Image
          src="/img/logo.webp"
          alt="Sydney Liveability AI logo"
          fill
          sizes={compact ? "112px" : "128px"}
          className="object-contain"
          priority
        />
      </motion.div>
    </motion.div>
  );
}
