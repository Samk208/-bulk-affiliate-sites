<?php
/*
Template Name: Homepage
Template Post Type: page
*/

get_header(); ?>

<div id="aff-homepage">

    <!-- ========== HERO SECTION ========== -->
    <section class="aff-hero">
        <div class="aff-hero-inner">
            <h1 class="aff-hero-title"><?php bloginfo( 'name' ); ?></h1>
            <p class="aff-hero-tagline"><?php bloginfo( 'description' ); ?></p>
            <?php
            $best_products = get_category_by_slug( 'best-products' );
            $cta_url = $best_products ? get_category_link( $best_products->term_id ) : '#categories';
            ?>
            <a href="<?php echo esc_url( $cta_url ); ?>" class="aff-hero-cta">Browse Expert Reviews &rarr;</a>
            <div class="aff-trust-badges">
                <span class="aff-badge">&#10003; Expert Reviewed</span>
                <span class="aff-badge">&#10003; Updated <?php echo date( 'F Y' ); ?></span>
                <span class="aff-badge">&#10003; No Sponsored Rankings</span>
            </div>
        </div>
    </section>

    <!-- ========== CATEGORY CARDS ========== -->
    <section class="aff-section" id="categories">
        <div class="aff-container">
            <h2 class="aff-section-title">Explore by Topic</h2>
            <div class="aff-category-grid">
                <?php
                $category_descriptions = array(
                    'best-products'  => 'In-depth reviews and comparisons of top-rated products, tested and ranked by experts.',
                    'buying-guides'  => 'Everything you need to know before you buy — size guides, feature breakdowns, and budget picks.',
                    'how-to-guides'  => 'Step-by-step tutorials and practical advice from hands-on experience.',
                    'tips-and-care'  => 'Daily care routines, health tips, and expert-backed best practices.',
                );
                $display_cats = get_categories( array(
                    'exclude'    => array( 1 ), // exclude Uncategorized
                    'orderby'    => 'count',
                    'order'      => 'DESC',
                    'hide_empty' => false,
                ) );
                foreach ( $display_cats as $cat ) :
                    $desc = isset( $category_descriptions[ $cat->slug ] ) ? $category_descriptions[ $cat->slug ] : $cat->description;
                    $icon = '&#128218;'; // default book icon
                    if ( $cat->slug === 'best-products' )  $icon = '&#11088;';
                    if ( $cat->slug === 'buying-guides' )   $icon = '&#128722;';
                    if ( $cat->slug === 'how-to-guides' )   $icon = '&#128736;';
                    if ( $cat->slug === 'tips-and-care' )   $icon = '&#128153;';
                ?>
                <a href="<?php echo esc_url( get_category_link( $cat->term_id ) ); ?>" class="aff-cat-card">
                    <span class="aff-cat-icon"><?php echo $icon; ?></span>
                    <h3 class="aff-cat-name"><?php echo esc_html( $cat->name ); ?></h3>
                    <p class="aff-cat-desc"><?php echo esc_html( $desc ); ?></p>
                    <span class="aff-cat-count"><?php echo $cat->count; ?> articles</span>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
    </section>

    <!-- ========== LATEST ARTICLES ========== -->
    <section class="aff-section aff-section-alt">
        <div class="aff-container">
            <h2 class="aff-section-title">Latest Articles</h2>
            <div class="aff-articles-grid">
                <?php
                $latest = new WP_Query( array(
                    'posts_per_page' => 6,
                    'post_status'    => 'publish',
                    'category__not_in' => array( 1 ),
                ) );
                if ( $latest->have_posts() ) :
                    while ( $latest->have_posts() ) : $latest->the_post();
                        $cats = get_the_category();
                        $cat_name = ! empty( $cats ) ? $cats[0]->name : '';
                ?>
                <article class="aff-article-card">
                    <?php if ( has_post_thumbnail() ) : ?>
                        <div class="aff-article-thumb">
                            <a href="<?php the_permalink(); ?>">
                                <?php the_post_thumbnail( 'medium_large' ); ?>
                            </a>
                        </div>
                    <?php endif; ?>
                    <div class="aff-article-body">
                        <?php if ( $cat_name ) : ?>
                            <span class="aff-article-cat"><?php echo esc_html( $cat_name ); ?></span>
                        <?php endif; ?>
                        <h3 class="aff-article-title">
                            <a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
                        </h3>
                        <p class="aff-article-excerpt"><?php echo wp_trim_words( get_the_excerpt(), 20 ); ?></p>
                        <span class="aff-article-date"><?php echo get_the_date(); ?></span>
                    </div>
                </article>
                <?php
                    endwhile;
                    wp_reset_postdata();
                else :
                ?>
                <p class="aff-no-content">Articles coming soon — expert reviews are being prepared.</p>
                <?php endif; ?>
            </div>
        </div>
    </section>

    <!-- ========== POPULAR PICKS ========== -->
    <?php
    $best_cat = get_category_by_slug( 'best-products' );
    $popular = new WP_Query( array(
        'posts_per_page' => 3,
        'post_status'    => 'publish',
        'cat'            => $best_cat ? $best_cat->term_id : 0,
    ) );
    if ( $popular->have_posts() ) :
    ?>
    <section class="aff-section">
        <div class="aff-container">
            <h2 class="aff-section-title">Popular Reviews</h2>
            <div class="aff-popular-grid">
                <?php while ( $popular->have_posts() ) : $popular->the_post(); ?>
                <div class="aff-popular-card">
                    <?php if ( has_post_thumbnail() ) : ?>
                        <div class="aff-popular-thumb">
                            <a href="<?php the_permalink(); ?>">
                                <?php the_post_thumbnail( 'medium' ); ?>
                            </a>
                        </div>
                    <?php endif; ?>
                    <div class="aff-popular-body">
                        <h3 class="aff-popular-title">
                            <a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
                        </h3>
                        <p class="aff-popular-excerpt"><?php echo wp_trim_words( get_the_excerpt(), 25 ); ?></p>
                        <a href="<?php the_permalink(); ?>" class="aff-popular-cta">Read Full Review &rarr;</a>
                    </div>
                </div>
                <?php endwhile; wp_reset_postdata(); ?>
            </div>
        </div>
    </section>
    <?php endif; ?>

    <!-- ========== ABOUT / CTA SECTION ========== -->
    <section class="aff-section aff-section-alt aff-about">
        <div class="aff-container aff-about-inner">
            <h2 class="aff-section-title">Why <?php bloginfo( 'name' ); ?>?</h2>
            <p class="aff-about-text">
                We test products hands-on, research the science, and write guides that help you
                make confident decisions. No sponsored rankings. No pay-to-play reviews.
                Just honest recommendations backed by real-world experience.
            </p>
            <div class="aff-about-stats">
                <?php
                $total_posts = wp_count_posts()->publish;
                $total_cats  = count( $display_cats );
                ?>
                <div class="aff-stat">
                    <span class="aff-stat-number"><?php echo $total_posts; ?>+</span>
                    <span class="aff-stat-label">Expert Reviews</span>
                </div>
                <div class="aff-stat">
                    <span class="aff-stat-number"><?php echo $total_cats; ?></span>
                    <span class="aff-stat-label">Topic Areas</span>
                </div>
                <div class="aff-stat">
                    <span class="aff-stat-number">2026</span>
                    <span class="aff-stat-label">Updated Monthly</span>
                </div>
            </div>
        </div>
    </section>

    <!-- ========== TRUST SECTION ========== -->
    <section class="aff-trust-section">
        <div class="aff-container">
            <div class="aff-trust-grid">
                <div class="aff-trust-item">
                    <span class="aff-trust-icon">&#128269;</span>
                    <strong>Research-Backed</strong>
                    <p>Every recommendation cites veterinary studies, manufacturer specs, and expert opinions.</p>
                </div>
                <div class="aff-trust-item">
                    <span class="aff-trust-icon">&#128736;</span>
                    <strong>Hands-On Testing</strong>
                    <p>We test products in real-world conditions before recommending them to you.</p>
                </div>
                <div class="aff-trust-item">
                    <span class="aff-trust-icon">&#128197;</span>
                    <strong>Regularly Updated</strong>
                    <p>Articles are reviewed and updated monthly to reflect the latest products and research.</p>
                </div>
            </div>
        </div>
    </section>

</div>

<?php get_footer(); ?>
