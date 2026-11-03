-- Designer reviews and the "engagement" that has to happen before a review is allowed.
-- Kept in its own file (not schema.sql) so nobody's shared schema has to change.
-- Every statement is IF NOT EXISTS, so it is safe to run on every start-up.

-- ENGAGEMENT: a customer hires an interior designer for a job.
--   requested -> ongoing (designer accepts) -> completed (designer marks it done)
--   requested -> declined (designer says no) / cancelled (customer withdraws)
create table if not exists engagement(
    id integer primary key autoincrement,
    customer_id integer not null,
    designer_id integer not null,
    idp_id integer,                                  -- optional: the portfolio project that inspired it
    title text not null,
    message text not null default '',
    status text not null default 'requested'
        check (status in ('requested', 'ongoing', 'completed', 'declined', 'cancelled')),
    created timestamp not null default current_timestamp,
    updated timestamp not null default current_timestamp,
    completed_at timestamp,
    foreign key (customer_id) references customer (cust_id) on delete cascade,
    foreign key (designer_id) references designer (userID) on delete cascade,
    foreign key (idp_id) references idp (id) on delete set null
);

-- REVIEW: one per completed engagement.
create table if not exists review(
    id integer primary key autoincrement,
    engagement_id integer not null unique,           -- unique = at most one review per job
    customer_id integer not null,
    designer_id integer not null,
    rating integer not null check (rating between 1 and 5),
    comment text not null default '',
    sentiment real,                                  -- -1 (very negative) .. +1 (very positive), from the text
    aspects text not null default '[]',              -- JSON list of {"aspect": "...", "polarity": +1/-1}
    edit_count integer not null default 0,
    designer_reply text,
    replied_at timestamp,
    status text not null default 'visible' check (status in ('visible', 'hidden')),
    hidden_reason text,
    moderated_at timestamp,
    reported_reason text,                            -- set when a designer reports the review
    reported_at timestamp,
    created timestamp not null default current_timestamp,
    updated timestamp not null default current_timestamp,
    foreign key (engagement_id) references engagement (id) on delete cascade,
    foreign key (customer_id) references customer (cust_id) on delete cascade,
    foreign key (designer_id) references designer (userID) on delete cascade
);

-- A review is only allowed for a COMPLETED engagement that belongs to the same customer and designer.
-- Enforced here as well as in the controller, so no code path can skip the rule.
create trigger if not exists review_requires_completed_engagement
before insert on review
when not exists (
    select 1 from engagement e
    where e.id = new.engagement_id and e.status = 'completed'
      and e.customer_id = new.customer_id and e.designer_id = new.designer_id
)
begin
    select raise(abort, 'A review needs a completed engagement between this customer and designer');
end;

create index if not exists ix_engagement_customer on engagement (customer_id);
create index if not exists ix_engagement_designer on engagement (designer_id, status);
create index if not exists ix_review_designer on review (designer_id, status);
create index if not exists ix_review_created on review (created);
